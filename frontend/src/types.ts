export interface EvaluationMessage {
  phase: "data_collection" | "reasoning" | "done";
  step: number;
  step_name: string;
  agent: string;
  status: "running" | "complete" | "done" | "error";
  message: string;
  output: string | null;
  reasoning?: string;
}

export interface ProductSubmission {
  name: string;
  description: string;
  price: number;
  category: string;
  claims: string;
  image: string | null;
  image_path: string | null;
}

export interface SimilarProduct {
  sku: string;
  name: string;
  brand: string;
  category: string;
  similarity_score: number;
  image_path: string;
  claims: string;
  price: number;
}

export interface EnrichedProduct {
  sku: string;
  name: string;
  brand: string;
  category: string;
  similarity_score: number;
  image_path: string;
  claims: string;
  ingredients: string;
  annual_revenue: number;
  weekly_units: number;
  velocity_rank: number;
  yoy_growth: number;
  stores_carrying: number;
  trend: string;
  price: number;
  cost: number;
  margin_pct: number;
  status: string;
  shelf_position: string;
  vendor_fill_rate: number;
  vendor_otif_score: number;
  vendor_compliance_rating: string;
  vendor_relationship_tier: string;
  vendor_open_chargebacks: number;
}

export interface StepState {
  step: number;
  stepName: string;
  status: "pending" | "running" | "complete" | "error";
  message: string;
  output: string | null;
  reasoning?: string;
  startedAt?: number;
  completedAt?: number;
}
