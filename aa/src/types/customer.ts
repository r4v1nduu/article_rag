export interface Customer {
  _id: string;
  name: string;
  description?: string;
  createdAt: Date;
}

export type CustomerCreate = Omit<Customer, "_id" | "createdAt">;
export type CustomerUpdate = Partial<CustomerCreate>;
