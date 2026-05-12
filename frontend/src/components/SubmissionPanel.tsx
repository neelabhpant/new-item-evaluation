import { type FormEvent, useEffect, useRef, useState } from "react";

export interface SubmissionInitial {
  name?: string;
  description?: string;
  price?: number;
  category?: string;
  claims?: string[];
}

interface Props {
  onSubmit: (data: {
    name: string;
    description: string;
    price: number;
    category: string;
    claims: string;
    image: string | null;
  }) => void;
  isRunning: boolean;
  /** When this object changes (new identity), the form resets to these values. */
  initialValues?: SubmissionInitial & { _version?: number };
}

const CATEGORIES = [
  "Auto-detect",
  "Protein Bars",
  "Energy Bars",
  "Granola Bars",
  "Nut Bars",
  "Snack Bars",
  "Chocolate & Candy",
  "Cookies",
  "Chips",
  "Potato Chips",
  "Tortilla Chips",
  "Veggie Snacks",
  "Popcorn",
  "Crackers",
  "Rice Cakes",
  "Pretzels",
  "Trail Mix",
  "Fruit Snacks",
  "Cheese Snacks",
  "Puffed Snacks",
  "Other Snacks",
];

const CLAIM_OPTIONS = [
  "Organic",
  "Non-GMO",
  "Gluten-Free",
  "Plant-Based",
  "High Protein",
  "No Artificial Flavors",
  "No Artificial Colors",
  "Vegan",
  "Kosher",
  "Low Sugar",
];

export default function SubmissionPanel({ onSubmit, isRunning, initialValues }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("Auto-detect");
  const [selectedClaims, setSelectedClaims] = useState<string[]>([]);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Sync form state when caller pushes new initialValues (e.g. "Branch into new run").
  useEffect(() => {
    if (!initialValues) return;
    if (initialValues.name !== undefined) setName(initialValues.name);
    if (initialValues.description !== undefined) setDescription(initialValues.description);
    if (initialValues.price !== undefined) setPrice(String(initialValues.price));
    if (initialValues.category !== undefined) setCategory(initialValues.category || "Auto-detect");
    if (initialValues.claims !== undefined) setSelectedClaims(initialValues.claims);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValues?._version]);

  // Prevent the browser from navigating if the user drops a file anywhere
  // outside the drop zone (default behavior is to open the file in the tab).
  useEffect(() => {
    const block = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  function processFile(file: File) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      setImagePreview(result);
      setImageBase64(result.split(",")[1]);
    };
    reader.readAsDataURL(file);
  }

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!dragActive) setDragActive(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }

  function toggleClaim(claim: string) {
    setSelectedClaims((prev) =>
      prev.includes(claim) ? prev.filter((c) => c !== claim) : [...prev, claim]
    );
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      name,
      description,
      price: parseFloat(price),
      category,
      claims: selectedClaims.join(", "),
      image: imageBase64,
    });
  }

  return (
    <div className="bg-white rounded-lg border border-gray-border p-5 h-fit">
      <h2 className="text-base font-semibold text-gray-900 mb-4">Product Submission</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-text mb-1">Product Image</label>
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={handleDragOver}
            onDragEnter={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
              dragActive
                ? "border-orange-brand bg-orange-50"
                : "border-gray-border hover:border-orange-brand"
            }`}
          >
            {imagePreview ? (
              <img src={imagePreview} alt="Preview" className="w-full h-40 object-contain rounded pointer-events-none" />
            ) : (
              <div className="text-gray-400 text-sm pointer-events-none">
                <svg className="w-8 h-8 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.91m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                </svg>
                {dragActive ? "Drop the image" : "Drop an image or click to upload"}
              </div>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleImageChange} />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-text mb-1">Product Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-brand/50 focus:border-orange-brand"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-text mb-1">Price</label>
          <div className="relative">
            <span className="absolute left-3 top-2 text-sm text-gray-text">$</span>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full border border-gray-border rounded pl-7 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-brand/50 focus:border-orange-brand"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-text mb-1">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full border border-gray-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-brand/50 focus:border-orange-brand bg-white"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-text mb-2">Claims</label>
          <div className="flex flex-wrap gap-1.5">
            {CLAIM_OPTIONS.map((claim) => (
              <button
                key={claim}
                type="button"
                onClick={() => toggleClaim(claim)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  selectedClaims.includes(claim)
                    ? "bg-orange-brand text-white"
                    : "bg-gray-100 text-gray-text hover:bg-gray-200"
                }`}
              >
                {claim}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-text mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full border border-gray-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-brand/50 focus:border-orange-brand resize-none"
          />
        </div>

        <button
          type="submit"
          disabled={isRunning || !name}
          className="w-full bg-orange-brand text-white font-semibold py-2.5 rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
        >
          {isRunning ? "EVALUATING..." : "EVALUATE"}
        </button>
      </form>
    </div>
  );
}
