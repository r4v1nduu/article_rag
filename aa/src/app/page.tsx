"use client";

import React from "react";
import ArticleAddForm from "@/components/ArticleAddForm";
import Navbar from "@/components/Navbar";

export default function AddArticlePage() {
  const handleFormSubmit = () => {
    // Optional: redirect to manage page after successful submission
    // router.push('/manage');
  };

  return (
    <div className="min-h-screen">
      <Navbar currentPage="add" />

      <div className="max-w-4xl mx-auto py-12 sm:px-8 lg:px-12">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Add New Article</h1>
          <p className="mt-2">Create and add a new article to the system</p>
        </div>

        {/* Form */}
        <ArticleAddForm mode="create" onFormSubmit={handleFormSubmit} />
      </div>
    </div>
  );
}
