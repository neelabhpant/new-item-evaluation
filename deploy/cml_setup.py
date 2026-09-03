"""Create (or update) the Cloudera AI Jobs and Application for this project via cmlapi.

  python deploy/cml_setup.py            # create/update jobs + application
  python deploy/cml_setup.py --run      # ... and start the bootstrap job chain
  python deploy/cml_setup.py --public   # application reachable without Cloudera login

Runs inside a Cloudera AI session (uses CDSW_PROJECT_ID / CDSW_APIV2_KEY from the
environment). Idempotent: existing jobs/applications with the same names are updated.

This is the manual / re-deploy path. The same bootstrap is declared as AMP tasks in
.project-metadata.yaml at the repository root, which is what "New Project > AMPs" runs.

Project-level environment variables (Project Settings > Advanced) are the source
of truth for configuration; APP_ENV below only carries non-secret defaults that
are safe to override there.
"""

from __future__ import annotations

import json
import os
import sys

import cmlapi

RUNTIME = os.getenv(
    "CML_RUNTIME",
    "docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.10-standard:2026.08.1-b5",
)
APP_NAME = os.getenv("CML_APP_NAME", "New Item Evaluation")
APP_SUBDOMAIN = os.getenv("CML_APP_SUBDOMAIN", "new-item-eval")

# Non-secret defaults. Secrets (IMPALA_PASSWORD / CDP_TOKEN / OPENSEARCH_PASSWORD) and
# environment-specific values belong in the project environment, not here.
COMMON_ENV = {
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "caii"),
    "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
    "LLM_MODEL": os.getenv("LLM_MODEL", ""),
    "LLM_TEMPERATURE": os.getenv("LLM_TEMPERATURE", "0.3"),
    "LLM_MAX_TOKENS": os.getenv("LLM_MAX_TOKENS", "2048"),
    "OPENSEARCH_MODE": os.getenv("OPENSEARCH_MODE", "embedded"),
    "OPENSEARCH_URL": os.getenv("OPENSEARCH_URL", "http://127.0.0.1:9200"),
    "OPENSEARCH_INDEX": os.getenv("OPENSEARCH_INDEX", "product-catalog"),
    "OPENSEARCH_VERSION": os.getenv("OPENSEARCH_VERSION", "2.11.0"),
    "OPENSEARCH_DATA_DIR": os.getenv("OPENSEARCH_DATA_DIR", "/tmp/opensearch-data"),
    "OPENSEARCH_JAVA_OPTS": os.getenv("OPENSEARCH_JAVA_OPTS", "-Xms1g -Xmx1g"),
    "DB_BACKEND": os.getenv("DB_BACKEND", "impala"),
    "IMPALA_HOST": os.getenv("IMPALA_HOST", ""),
    "IMPALA_PORT": os.getenv("IMPALA_PORT", "443"),
    "IMPALA_HTTP_PATH": os.getenv("IMPALA_HTTP_PATH", "cliservice"),
    "IMPALA_DATABASE": os.getenv("IMPALA_DATABASE", "new_item_eval"),
    "CLIP_CACHE_DIR": os.getenv("CLIP_CACHE_DIR", "/home/cdsw/.cache/clip"),
    "CML_JWT_FALLBACK_PATH": os.getenv("CML_JWT_FALLBACK_PATH", "/home/cdsw/.secrets/jwt.json"),
    "CREWAI_TELEMETRY_OPT_OUT": "true",
    "OTEL_SDK_DISABLED": "true",
}
COMMON_ENV = {k: v for k, v in COMMON_ENV.items() if v}

JOBS = [
    # name, script, cpu, memory(GB), timeout(s)
    ("nie-01-install-deps", "deploy/install_deps.py", 4, 8, 3600),
    ("nie-02-fetch-images", "scripts/fetch_images.py", 2, 4, 1800),
    ("nie-03-embed-catalog", "deploy/bootstrap_embed.py", 4, 8, 1800),
    ("nie-04-init-tables", "backend/data/init_db.py", 2, 4, 900),
]
# Independent, scheduled: copies a valid workload token to project storage for the Application.
TOKEN_JOB = ("nie-05-refresh-token", "deploy/save_session_token.py", 1, 2, 300, "0 */6 * * *")


def main() -> None:
    client = cmlapi.default_client()
    pid = os.environ["CDSW_PROJECT_ID"]

    existing_jobs = {j.name: j for j in client.list_jobs(pid, page_size=200).jobs}
    parent_id = None
    first_job = None
    for name, script, cpu, mem, timeout in JOBS:
        body = cmlapi.CreateJobRequest(
            project_id=pid, name=name, script=script, kernel="python3",
            runtime_identifier=RUNTIME, cpu=cpu, memory=mem, timeout=timeout,
            parent_job_id=parent_id, environment=COMMON_ENV,
        )
        if name in existing_jobs:
            job = existing_jobs[name]
            # update_* take the resource type and a JSON-encoded environment string
            client.update_job(cmlapi.Job(
                name=name, script=script, runtime_identifier=RUNTIME, cpu=cpu, memory=mem, timeout=timeout,
                parent_id=parent_id, environment=json.dumps(COMMON_ENV),
            ), pid, job.id)
            print(f"updated job  {name} ({job.id})")
        else:
            job = client.create_job(body, pid)
            print(f"created job  {name} ({job.id})")
        first_job = first_job or job
        parent_id = job.id

    name, script, cpu, mem, timeout, schedule = TOKEN_JOB
    if name in existing_jobs:
        client.update_job(cmlapi.Job(name=name, script=script, runtime_identifier=RUNTIME, cpu=cpu, memory=mem,
                                     timeout=timeout, schedule=schedule, environment=json.dumps(COMMON_ENV)), pid, existing_jobs[name].id)
        print(f"updated job  {name} (schedule {schedule})")
    else:
        job = client.create_job(cmlapi.CreateJobRequest(project_id=pid, name=name, script=script, kernel="python3",
                                                        runtime_identifier=RUNTIME, cpu=cpu, memory=mem, timeout=timeout,
                                                        schedule=schedule, environment=COMMON_ENV), pid)
        print(f"created job  {name} ({job.id}, schedule {schedule})")

    apps = {a.name: a for a in client.list_applications(pid, page_size=100).applications}
    app_body = cmlapi.CreateApplicationRequest(
        project_id=pid, name=APP_NAME, subdomain=APP_SUBDOMAIN, description="Multimodal new item evaluation (CLIP + OpenSearch k-NN + Iceberg/Impala + Cloudera AI Inference agents)",
        script="deploy/app.py", kernel="python3", runtime_identifier=RUNTIME,
        cpu=int(os.getenv("CML_APP_CPU", "4")), memory=int(os.getenv("CML_APP_MEMORY", "16")),
        bypass_authentication="--public" in sys.argv, environment=COMMON_ENV,
    )
    if APP_NAME in apps:
        app = apps[APP_NAME]
        client.update_application(cmlapi.Application(
            name=APP_NAME, subdomain=APP_SUBDOMAIN, script="deploy/app.py", runtime_identifier=RUNTIME,
            cpu=int(os.getenv("CML_APP_CPU", "4")), memory=int(os.getenv("CML_APP_MEMORY", "16")),
            bypass_authentication="--public" in sys.argv, environment=json.dumps(COMMON_ENV),
        ), pid, app.id)
        print(f"updated app  {APP_NAME} ({app.id})")
    else:
        app = client.create_application(app_body, pid)
        print(f"created app  {APP_NAME} ({app.id})")
    print(f"application URL: https://{APP_SUBDOMAIN}.{os.environ.get('CDSW_DOMAIN', '<workbench-domain>')}")

    if "--run" in sys.argv and first_job is not None:
        run = client.create_job_run(cmlapi.CreateJobRunRequest(project_id=pid, job_id=first_job.id), pid, first_job.id)
        print(f"started {first_job.name} run {run.id}; downstream jobs run automatically on success")


if __name__ == "__main__":
    main()
