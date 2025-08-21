"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import Navbar from "@/components/Navbar";
import ArticleAddForm from "@/components/ArticleAddForm";
import { Article } from "@/types/article";
import { ArrowLeftIcon } from "@heroicons/react/24/outline";

export default function EditArticlePage() {
  const router = useRouter();
  const params = useParams();
  const articleId = params.id as string;

  const [article, setArticle] = useState<Article | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notification, setNotification] = useState<{
    type: "success" | "error" | "warning";
    message: string;
  } | null>(null);

  const showNotification = (
    type: "success" | "error" | "warning",
    message: string
  ) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  // Fetch article data
  useEffect(() => {
    const fetchArticle = async () => {
      try {
        setIsLoading(true);
        const response = await fetch(`/api/articles/${articleId}`);
        if (!response.ok) {
          throw new Error("Failed to fetch article");
        }
        const result = await response.json();
        if (!result.success) {
          throw new Error(result.error || "Failed to fetch article");
        }
        setArticle(result.data);
      } catch (error) {
        showNotification("error", "Failed to load article");
        console.error("Error fetching article:", error);
      } finally {
        setIsLoading(false);
      }
    };

    if (articleId) {
      fetchArticle();
    }
  }, [articleId]);

  const handleArticleUpdated = () => {
    // Navigate back after successful update
    setTimeout(() => {
      router.back();
    }, 1500);
  };

  const handleCancel = () => {
    router.back();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Navbar currentPage="home" />
        <div className="max-w-4xl mx-auto py-8 px-6 sm:px-8 lg:px-12">
          <div className="bg-card rounded-lg border border-border p-6">
            <div className="flex items-center justify-center py-12">
              <svg
                className="animate-spin h-8 w-8 text-muted-foreground"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              <span className="ml-2 text-muted-foreground">
                Loading article...
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Navbar currentPage="home" />
        <div className="max-w-4xl mx-auto py-8 px-6 sm:px-8 lg:px-12">
          <div className="bg-card rounded-lg border border-border p-6">
            <div className="text-center py-12">
              <p className="text-muted-foreground text-lg">Article not found</p>
              <Button onClick={handleCancel} className="mt-4" variant="outline">
                Go Back
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar currentPage="home" />
      <div className="max-w-4xl mx-auto py-8 px-6 sm:px-8 lg:px-12">
        {/* Notification */}
        {notification && (
          <div
            className={`mb-6 p-4 rounded-md ${
              notification.type === "success"
                ? "bg-green-50 text-green-700 border border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800"
                : notification.type === "error"
                ? "bg-red-50 text-red-700 border border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800"
                : "bg-yellow-50 text-yellow-700 border border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-300 dark:border-yellow-800"
            }`}
          >
            {notification.message}
          </div>
        )}

        {/* Header */}
        <div className="flex items-center mb-6">
          <Button
            onClick={handleCancel}
            variant="outline"
            size="sm"
            className="mr-4"
          >
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold text-foreground">Edit Article</h1>
        </div>

        {/* Reusable Form Component */}
        <ArticleAddForm
          mode="edit"
          initialData={article}
          onArticleUpdated={handleArticleUpdated}
          onCancel={handleCancel}
        />
      </div>
    </div>
  );
}
