export interface Product {
  _id: string;
  name: string;
  description?: string;
  createdAt: Date;
}

export type ProductCreate = Omit<Product, "_id" | "createdAt">;
export type ProductUpdate = Partial<ProductCreate>;
