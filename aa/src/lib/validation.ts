import { z } from "zod";

// Common string validation for reuse
const nonEmptyString = z.string().trim().min(1, { message: "Cannot be empty" });

// Schema for creating a new article
export const createArticleSchema = z.object({
  product: nonEmptyString,
  customer: nonEmptyString,
  subject: z.string().trim().min(1, { message: "Subject cannot be empty" }),
  body: z.string().trim().min(1, { message: "Body cannot be empty" }),
  date: z.string().datetime({ message: "Invalid date format" }),
});

// Schema for updating an existing article (all fields optional)
export const updateArticleSchema = z
  .object({
    product: nonEmptyString.optional(),
    customer: nonEmptyString.optional(),
    subject: z.string().trim().min(1).optional(),
    body: z.string().trim().min(1).optional(),
    date: z.string().datetime({ message: "Invalid date format" }).optional(),
  })
  .refine(
    (data) => Object.keys(data).length > 0,
    { message: "At least one field must be provided for an update" }
  );
