"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Navbar from "@/components/Navbar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { toast } from "@/lib/toast";
import { Customer, CustomerCreate } from "@/types/customer";
import { RefreshCw } from "lucide-react";

const fetchCustomers = async (): Promise<Customer[]> => {
  const res = await fetch("/api/customers");
  if (!res.ok) {
    throw new Error("Network response was not ok");
  }
  return res.json();
};

const createCustomer = async (customer: CustomerCreate) => {
  const res = await fetch("/api/customers", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(customer),
  });
  if (!res.ok) {
    throw new Error("Network response was not ok");
  }
  return res.json();
};

const updateCustomer = async (customer: Customer) => {
  const res = await fetch(`/api/customers/${customer._id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name: customer.name, description: customer.description }),
  });
  if (!res.ok) {
    throw new Error("Network response was not ok");
  }
  return res.json();
};

const deleteCustomer = async (id: string) => {
  const res = await fetch(`/api/customers/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Network response was not ok");
  }
  return res.json();
};

export default function ManageCustomers() {
  const queryClient = useQueryClient();
  const {
    data: customers,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<Customer[]>({
    queryKey: ["customers"],
    queryFn: fetchCustomers,
  });

  const createMutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      toast.success("Customer created successfully");
    },
    onError: () => {
      toast.error("Failed to create customer");
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      toast.success("Customer updated successfully");
    },
    onError: () => {
      toast.error("Failed to update customer");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      toast.success("Customer deleted successfully");
    },
    onError: () => {
      toast.error("Failed to delete customer");
    },
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [deletingCustomer, setDeletingCustomer] = useState<Customer | null>(
    null
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.warning("Customer name is required");
      return;
    }
    if (editingCustomer) {
      updateMutation.mutate({ ...editingCustomer, name, description });
    } else {
      createMutation.mutate({ name, description });
    }
    setName("");
    setDescription("");
    setEditingCustomer(null);
  };

  const handleEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    setName(customer.name);
    setDescription(customer.description || "");
  };

  const handleDelete = (customer: Customer) => {
    setDeletingCustomer(customer);
  };

  const confirmDelete = () => {
    if (deletingCustomer) {
      deleteMutation.mutate(deletingCustomer._id);
      setDeletingCustomer(null);
    }
  };


  return (
    <div className="min-h-screen">
      <Navbar currentPage="manage" />
        <div className="max-w-7xl mx-auto py-12 sm:px-8 lg:px-12">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-bold">Manage Customers</h1>
            <Button onClick={() => refetch()} disabled={isRefetching}>
              {isRefetching ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Refresh
            </Button>
          </div>
          <div className="mb-8">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Customer Name"
                />
              </div>
              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Customer Description"
                />
              </div>
              <Button type="submit">{editingCustomer ? "Update Customer" : "Add Customer"}</Button>
              {editingCustomer && (
                <Button variant="outline" onClick={() => setEditingCustomer(null)}>
                  Cancel
                </Button>
              )}
            </form>
          </div>
          <div>
            <h2 className="text-xl font-semibold mb-2">Customer List</h2>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                <span>Loading customers...</span>
              </div>
            ) : isError ? (
              <div className="text-red-500 text-center py-8">
                <p>Failed to load customers: {error instanceof Error ? error.message : "An unknown error occurred."}</p>
                <Button onClick={() => refetch()} className="mt-4">
                  Retry
                </Button>
              </div>
            ) : customers && customers.length > 0 ? (
              <ul className="space-y-2">
                {customers.map((customer) => (
                  <li key={customer._id} className="flex justify-between items-center p-2 border rounded">
                    <div>
                      <p className="font-bold">{customer.name}</p>
                      <p className="text-sm text-gray-500">{customer.description}</p>
                    </div>
                    <div className="space-x-2">
                      <Button variant="outline" size="sm" onClick={() => handleEdit(customer)}>
                        Edit
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => handleDelete(customer)}>
                        Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-center py-8">No customers found.</p>
            )}
          </div>
          <Dialog open={!!deletingCustomer} onOpenChange={(isOpen) => !isOpen && setDeletingCustomer(null)}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Are you sure you want to delete this customer?</DialogTitle>
                <DialogDescription>
                  This action cannot be undone. This will permanently delete the customer.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">Cancel</Button>
                </DialogClose>
                <Button variant="destructive" onClick={confirmDelete}>
                  Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>
  );
}
