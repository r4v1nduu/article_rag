"use client";

import React from "react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Users, ShoppingCart, FileText } from "lucide-react";

export default function ManageDashboardPage() {
  return (
    <div className="min-h-screen">
      <Navbar currentPage="manage" />

      <div className="max-w-7xl mx-auto py-12 sm:px-8 lg:px-12">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Management Dashboard</h1>
          <p className="mt-2">Manage your customers, products, and articles.</p>
        </div>

        {/* Management Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <Link href="/manage/customers">
            <Card className="">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Users className="mr-2" />
                  Manage Customers
                </CardTitle>
                <CardDescription>
                  Add, edit, and remove customers.
                </CardDescription>
              </CardHeader>
            </Card>
          </Link>
          <Link href="/manage/products">
            <Card className="">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <ShoppingCart className="mr-2" />
                  Manage Products
                </CardTitle>
                <CardDescription>
                  Add, edit, and remove products.
                </CardDescription>
              </CardHeader>
            </Card>
          </Link>
          <Link href="/manage/articles">
            <Card className="">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <FileText className="mr-2" />
                  Manage Articles
                </CardTitle>
                <CardDescription>View and manage all articles.</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  );
}
