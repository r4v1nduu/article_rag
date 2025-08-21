"use client";

import React, { useState, useCallback, useEffect } from "react";
import { ArticleCreate, ArticleUpdate, Article } from "@/types/article";
import { useCreateArticle, useUpdateArticle } from "@/hooks/useArticleQueries";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2Icon } from "lucide-react";
import { format } from "date-fns";
import { Calendar as CalendarIcon, Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Calendar } from "@/components/ui/calendar";
import { toast } from "@/lib/toast";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useQuery } from "@tanstack/react-query";
import { Customer } from "@/types/customer";
import { Product } from "@/types/product";

const fetchCustomers = async (): Promise<Customer[]> => {
  const res = await fetch("/api/customers");
  if (!res.ok) {
    throw new Error("Failed to fetch customers");
  }
  return res.json();
};

const fetchProducts = async (): Promise<Product[]> => {
  const res = await fetch("/api/products");
  if (!res.ok) {
    throw new Error("Failed to fetch products");
  }
  return res.json();
};

interface ArticleAddFormProps {
  mode?: "create" | "edit";
  initialData?: Article;
  onArticleCreated?: () => void;
  onArticleUpdated?: () => void;
  onFormSubmit?: () => void;
  onCancel?: () => void;
}

export default function ArticleAddForm({
  mode = "create",
  initialData,
  onArticleCreated,
  onArticleUpdated,
  onFormSubmit,
  onCancel,
}: ArticleAddFormProps) {
  const [formData, setFormData] = useState<ArticleCreate>({
    product: "",
    customer: "",
    subject: "",
    body: "",
    date: new Date().toISOString(),
  });

  const [productOpen, setProductOpen] = useState(false);
  const [customerOpen, setCustomerOpen] = useState(false);

  const { data: products, isLoading: productsLoading } = useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: fetchProducts,
  });
  const { data: customers, isLoading: customersLoading } = useQuery<Customer[]>({
    queryKey: ["customers"],
    queryFn: fetchCustomers,
  });

  const createArticleMutation = useCreateArticle();
  const updateArticleMutation = useUpdateArticle();

  // Initialize form data with initial data if provided
  useEffect(() => {
    if (mode === "edit" && initialData) {
      setFormData({
        product: initialData.product,
        customer: initialData.customer,
        subject: initialData.subject,
        body: initialData.body,
        date: initialData.date,
      });
    }
  }, [mode, initialData]);

  const resetForm = useCallback(() => {
    setFormData({
      product: "",
      customer: "",
      subject: "",
      body: "",
      date: new Date().toISOString(),
    });
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      const { product, customer, subject, body } = formData;
      if (
        !product.trim() ||
        !customer.trim() ||
        !subject.trim() ||
        !body.trim()
      ) {
        toast.warning("Please fill in all fields");
        return;
      }

      try {
        if (mode === "create") {
          await createArticleMutation.mutateAsync(formData);
          toast.success("Article created successfully!");
          resetForm();
          onArticleCreated?.();
        } else if (mode === "edit" && initialData) {
          const updateData: ArticleUpdate = {
            product: formData.product,
            customer: formData.customer,
            subject: formData.subject,
            body: formData.body,
            date: formData.date,
          };
          await updateArticleMutation.mutateAsync({
            id: initialData.id,
            data: updateData,
          });
          toast.success("Article updated successfully!");
          onArticleUpdated?.();
        }
        onFormSubmit?.();
      } catch {
        toast.error(
          mode === "create"
            ? "Failed to create article"
            : "Failed to update article"
        );
      }
    },
    [
      formData,
      mode,
      initialData,
      createArticleMutation,
      updateArticleMutation,
      resetForm,
      onArticleCreated,
      onArticleUpdated,
      onFormSubmit,
    ]
  );

  const isLoading =
    createArticleMutation.isPending || updateArticleMutation.isPending;

  return (
    <div className="bg-card rounded-lg border border-border">
      <div className="px-6 py-4 border-b border-border">
        <h2 className="text-lg font-semibold text-foreground">
          {mode === "create" ? "Create Article" : "Edit Article"}
        </h2>
      </div>

      <div className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="block text-sm font-medium text-foreground mb-2">
                Product <span className="text-red-500">*</span>
              </Label>
              <Popover open={productOpen} onOpenChange={setProductOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={productOpen}
                    className="w-full justify-between disabled:cursor-not-allowed"
                    disabled={isLoading || productsLoading}
                  >
                    {formData.product
                      ? products?.find(
                          (product) => product.name === formData.product
                        )?.name ?? "N/A"
                      : "Select product..."}
                    <ChevronsUpDown className="opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-full p-0">
                  <Command>
                    <CommandInput
                      placeholder="Search product..."
                      className="h-9"
                    />
                    <CommandList>
                      <CommandEmpty>No product found.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          key="n/a-product"
                          value="N/A"
                          onSelect={() => {
                            setFormData((prev) => ({ ...prev, product: "N/A" }));
                            setProductOpen(false);
                          }}
                        >
                          N/A
                          <Check
                            className={cn(
                              "ml-auto",
                              formData.product === "N/A"
                                ? "opacity-100"
                                : "opacity-0"
                            )}
                          />
                        </CommandItem>
                        {products?.map((product) => (
                          <CommandItem
                            key={product._id}
                            value={product.name}
                            onSelect={(currentValue) => {
                              setFormData((prev) => ({
                                ...prev,
                                product:
                                  currentValue === formData.product
                                    ? ""
                                    : currentValue,
                              }));
                              setProductOpen(false);
                            }}
                          >
                            {product.name}
                            <Check
                              className={cn(
                                "ml-auto",
                                formData.product === product.name
                                  ? "opacity-100"
                                  : "opacity-0"
                              )}
                            />
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <Label className="block text-sm font-medium text-foreground mb-2">
                Customer <span className="text-red-500">*</span>
              </Label>
              <Popover open={customerOpen} onOpenChange={setCustomerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={customerOpen}
                    className="w-full justify-between disabled:cursor-not-allowed"
                    disabled={isLoading || customersLoading}
                  >
                    {formData.customer
                      ? customers?.find(
                          (customer) => customer.name === formData.customer
                        )?.name ?? "N/A"
                      : "Select customer..."}
                    <ChevronsUpDown className="opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-full p-0">
                  <Command>
                    <CommandInput
                      placeholder="Search customer..."
                      className="h-9"
                    />
                    <CommandList>
                      <CommandEmpty>No customer found.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          key="n/a-customer"
                          value="N/A"
                          onSelect={() => {
                            setFormData((prev) => ({ ...prev, customer: "N/A" }));
                            setCustomerOpen(false);
                          }}
                        >
                          N/A
                          <Check
                            className={cn(
                              "ml-auto",
                              formData.customer === "N/A"
                                ? "opacity-100"
                                : "opacity-0"
                            )}
                          />
                        </CommandItem>
                        {customers?.map((customer) => (
                          <CommandItem
                            key={customer._id}
                            value={customer.name}
                            onSelect={(currentValue) => {
                              setFormData((prev) => ({
                                ...prev,
                                customer:
                                  currentValue === formData.customer
                                    ? ""
                                    : currentValue,
                              }));
                              setCustomerOpen(false);
                            }}
                          >
                            {customer.name}
                            <Check
                              className={cn(
                                "ml-auto",
                                formData.customer === customer.name
                                  ? "opacity-100"
                                  : "opacity-0"
                              )}
                            />
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>

          <div>
            <Label className="block text-sm font-medium text-foreground mb-2">
              Subject <span className="text-red-500">*</span>
            </Label>
            <Input
              type="text"
              value={formData.subject}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, subject: e.target.value }))
              }
              placeholder="Enter article subject"
              className="w-full disabled:cursor-not-allowed"
              disabled={isLoading}
            />
          </div>

          <div>
            <Label className="block text-sm font-medium text-foreground mb-2">
              Article Content <span className="text-red-500">*</span>
            </Label>
            <Textarea
              value={formData.body}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, body: e.target.value }))
              }
              placeholder="Enter article content"
              rows={4}
              className="w-full disabled:cursor-not-allowed resize-none"
              disabled={isLoading}
            />
          </div>

          <div>
            <Label className="block text-sm font-medium text-foreground mb-2">
              Date <span className="text-red-500">*</span>
            </Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  data-empty={!formData.date}
                  className="data-[empty=true]:text-muted-foreground w-full justify-start text-left font-normal disabled:cursor-not-allowed"
                  disabled={isLoading}
                >
                  <CalendarIcon />
                  {formData.date ? (
                    format(new Date(formData.date), "PPP")
                  ) : (
                    <span>Pick a date</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0">
                <Calendar
                  mode="single"
                  selected={formData.date ? new Date(formData.date) : undefined}
                  onSelect={(date) =>
                    setFormData((prev) => ({
                      ...prev,
                      date: date
                        ? date.toISOString()
                        : new Date().toISOString(),
                    }))
                  }
                />
              </PopoverContent>
            </Popover>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="submit"
              className="disabled:cursor-not-allowed"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2Icon className="animate-spin" />
                  {mode === "create" ? "Creating..." : "Updating..."}
                </>
              ) : mode === "create" ? (
                "Create Article"
              ) : (
                "Update Article"
              )}
            </Button>

            {mode === "create" ? (
              <Button
                type="button"
                onClick={resetForm}
                disabled={isLoading}
                variant="outline"
                className="disabled:cursor-not-allowed"
              >
                Reset
              </Button>
            ) : (
              onCancel && (
                <Button
                  type="button"
                  onClick={onCancel}
                  disabled={isLoading}
                  variant="outline"
                  className="disabled:cursor-not-allowed"
                >
                  Cancel
                </Button>
              )
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
