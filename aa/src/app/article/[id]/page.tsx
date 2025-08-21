"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Article } from "@/types/article";
import { ArrowLeftIcon } from "@heroicons/react/24/outline";

export default function ViewArticlePage() {
  const params = useParams();
  const router = useRouter();
  const articleId = params.id as string;

  const [article, setArticle] = useState<Article | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await fetch(`/api/articles/${articleId}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || `Failed to load article (${res.status})`);
        }
        const result = await res.json();
        if (!result.success) {
          throw new Error(result.error || "Failed to load article");
        }
        setArticle(result.data as Article);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setIsLoading(false);
      }
    };

    if (articleId) fetchArticle();
  }, [articleId]);

  const handleBack = () => router.back();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar currentPage="home" />
      <div className="max-w-5xl mx-auto py-8 px-6 sm:px-8 lg:px-12">
        <div className="flex items-center mb-6">
          <Button onClick={handleBack} variant="outline" size="sm" className="mr-4">
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold">Article Details</h1>
        </div>

        {isLoading ? (
          <Card>
            <CardContent className="py-16 text-center text-muted-foreground">
              Loading article...
            </CardContent>
          </Card>
        ) : error ? (
          <Card>
            <CardContent className="py-12">
              <p className="text-red-500">{error}</p>
              <Button onClick={() => router.refresh()} className="mt-4" variant="outline">
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : !article ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-muted-foreground">Article not found</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="break-words">{article.subject}</CardTitle>
                <CardDescription>
                  <span className="mr-4"><strong>Product:</strong> {article.product}</span>
                  <span className="mr-4"><strong>Customer:</strong> {article.customer}</span>
                  <span><strong>Date:</strong> {new Date(article.date).toLocaleString()}</span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-muted-foreground">
                  <div>
                    <div><span className="font-medium text-foreground">ID:</span> <code className="break-all">{article.id}</code></div>
                  </div>
                  <div className="md:text-right">
                    {article.created_at && (
                      <div><span className="font-medium text-foreground">Created:</span> {new Date(article.created_at).toLocaleString()}</div>
                    )}
                    {article.updated_at && (
                      <div><span className="font-medium text-foreground">Updated:</span> {new Date(article.updated_at).toLocaleString()}</div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Content</CardTitle>
                <CardDescription>Full article body</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="whitespace-pre-wrap leading-relaxed text-foreground">
                  {article.body}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
