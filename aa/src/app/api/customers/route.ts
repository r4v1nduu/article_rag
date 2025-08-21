import { NextResponse } from "next/server";
import { getCustomersCollection } from "@/lib/database";
import { z } from "zod";
import { CustomerCreate } from "@/types/customer";

const customerSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
});

export async function GET() {
  try {
    const collection = await getCustomersCollection();
    const customers = await collection.find({}).toArray();
    return NextResponse.json(customers);
  } catch (error) {
    console.error("Failed to fetch customers:", error);
    return NextResponse.json(
      { message: "Failed to fetch customers" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const json = await request.json();
    const data: CustomerCreate = customerSchema.parse(json);

    const collection = await getCustomersCollection();
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
    console.error("Failed to create customer:", error);
    return NextResponse.json(
      { message: "Failed to create customer" },
      { status: 500 }
    );
  }
}
