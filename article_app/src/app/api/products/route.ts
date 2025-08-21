import { NextResponse } from "next/server";
import { getProductsCollection } from "@/lib/database";
import { z } from "zod";

const productSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
});

export async function GET() {
  try {
    const collection = await getProductsCollection();
    const products = await collection.find({}).toArray();
    return NextResponse.json(products);
  } catch (error) {
    console.error("Failed to fetch products:", error);
    return NextResponse.json(
      { message: "Failed to fetch products" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const json = await request.json();
    const data = productSchema.parse(json);

    const collection = await getProductsCollection();
    const result = await collection.insertOne({
      ...data,
      createdAt: new Date(),
    });

    return NextResponse.json(
      { ...data, _id: result.insertedId },
      { status: 201 }
    );
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ errors: error.issues }, { status: 400 });
    }
    console.error("Failed to create product:", error);
    return NextResponse.json(
      { message: "Failed to create product" },
      { status: 500 }
    );
  }
}
