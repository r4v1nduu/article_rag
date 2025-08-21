"use client";

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  PencilIcon,
  TrashIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";
import { Article, SearchResponse } from "@/types/article";
import { useArticles, useDeleteArticle } from "@/hooks/useArticleQueries";
import { Button } from "@/components/ui/button";
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
import { highlightText, getSnippets } from "@/lib/highlight";

interface ArticleListTableProps {
  searchResults?: SearchResponse | null;
  searchAttempted?: boolean;
  isSearchView: boolean;
  refreshTrigger?: number;
  onRefreshComplete?: () => void;
  showActions?: boolean;
}

export default function ArticleListTable({
  searchResults,
  searchAttempted,
  isSearchView,
  refreshTrigger,
  onRefreshComplete,
  showActions = false,
}: ArticleListTableProps) {
  const router = useRouter();
  const [first, setFirst] = useState(0);
  const [rows] = useState(20);
  const [deletingArticle, setDeletingArticle] = useState<Article | null>(null);

  const { data: articlesData, refetch, isLoading, error } = useArticles(first, rows);
  const deleteArticleMutation = useDeleteArticle();

  const displayedArticles = isSearchView
    ? searchResults?.results ?? []
    : articlesData?.data ?? [];
  const totalRecords = isSearchView
    ? searchResults?.total ?? 0
    : articlesData?.total ?? 0;

  React.useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      refetch().then(() => onRefreshComplete?.());
    }
  }, [refreshTrigger, refetch, onRefreshComplete]);

  // Debug logging
  React.useEffect(() => {
    console.log('ArticleListTable Debug:', {
      isSearchView,
      displayedArticles: displayedArticles.length,
      totalRecords,
      isLoading,
      error: error?.message,
      articlesData
    });
  }, [isSearchView, displayedArticles.length, totalRecords, isLoading, error, articlesData]);

  const handleEditArticle = useCallback(
    (article: Article) => {
      router.push(`/edit/${article.id}`);
    },
    [router]
  );

  const startDelete = useCallback((article: Article) => {
    setDeletingArticle(article);
  }, []);

  const handleDeleteArticle = useCallback(async () => {
    if (!deletingArticle) return;

    try {
      await deleteArticleMutation.mutateAsync(deletingArticle.id);
      setDeletingArticle(null);
      toast.success("Article deleted successfully!");
    } catch {
      toast.error("Failed to delete article");
    }
  }, [deletingArticle, deleteArticleMutation]);

  const totalPages = Math.ceil(totalRecords / rows);
  const currentPage = Math.floor(first / rows) + 1;

  const onPageChangeNew = (newPage: number) => {
    const newFirst = (newPage - 1) * rows;
    setFirst(newFirst);
  };

  const renderArticleBody = (article: Article) => {
    if (isSearchView && searchResults?.query) {
      const snippets = getSnippets(article.body, searchResults.query);
      return (
        <div>
          {snippets.map((snippet, index) => (
            <p
              key={index}
              className="text-foreground text-sm leading-relaxed mb-2"
            >
              {highlightText(snippet, searchResults.query)}
            </p>
          ))}
        </div>
      );
    }
    return (
      <p className="text-foreground text-sm leading-relaxed">
        {article.body.length > 200
          ? `${article.body.substring(0, 200)}...`
          : article.body}
      </p>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-card rounded-lg border border-border p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-foreground">
            {isSearchView ? "Search Results" : "All Articles"}
          </h2>
          {(isSearchView || totalRecords > 0) && (
            <div className="text-sm text-muted-foreground">
              <span className="font-medium">{totalRecords} results</span>
            </div>
          )}
        </div>

        {/* Pagination Controls Top */}
        {totalPages > 1 && (
          <div className="flex justify-end mb-6">
            <div className="flex items-center space-x-2">
              <Button
                onClick={() => onPageChangeNew(currentPage - 1)}
                disabled={currentPage === 1}
                variant="outline"
                size="sm"
                className="text-blue-600 border-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:border-blue-400 dark:hover:bg-blue-900/20"
              >
                Prev Page
              </Button>
              <Button
                onClick={() => onPageChangeNew(currentPage + 1)}
                disabled={currentPage === totalPages}
                variant="outline"
                size="sm"
                className="text-blue-600 border-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:border-blue-400 dark:hover:bg-blue-900/20"
              >
                Next Page
              </Button>
            </div>
          </div>
        )}

        {/* Article List */}
        <div className="space-y-4">
          {isLoading ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-lg">Loading articles...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-500 text-lg">Error loading articles. Please try again.</p>
              <p className="text-red-400 text-sm mt-2">
                {error.message || "Database connection may be unavailable"}
              </p>
              <Button 
                onClick={() => refetch()} 
                variant="outline" 
                className="mt-4"
              >
                Retry
              </Button>
            </div>
          ) : isSearchView && searchAttempted && displayedArticles.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-lg">
                No matching results found.
              </p>
            </div>
          ) : displayedArticles.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-lg">No articles found.</p>
            </div>
          ) : (
            displayedArticles.map((article) => (
              <div
                key={article.id}
                className="border-b border-border pb-6 last:border-b-0 last:pb-0"
              >
                {/* Article Item Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <Link href={`/article/${article.id}`}>
                      <h3 className="text-lg font-medium text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
                        {isSearchView && searchResults?.query
                          ? highlightText(article.subject, searchResults.query)
                          : article.subject}
                      </h3>
                    </Link>
                    <div className="flex items-center space-x-4 mt-1">
                      <span className="text-sm text-muted-foreground">
                        <strong>Product:</strong> {article.product}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        <strong>Customer:</strong> {article.customer}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {new Date(article.date).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 break-all">
                      <strong>ID:</strong> <code>{article.id}</code>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  {showActions && (
                    <div className="flex items-center space-x-2 ml-4">
                      <Button
                        onClick={() => handleEditArticle(article)}
                        variant="outline"
                        size="sm"
                        className="text-green-600 border-green-600 hover:bg-green-50 dark:text-green-400 dark:border-green-400 dark:hover:bg-green-900/20"
                      >
                        <PencilIcon className="h-4 w-4 mr-1" />
                        Edit
                      </Button>
                      <Button
                        onClick={() => startDelete(article)}
                        variant="outline"
                        size="sm"
                        className="text-red-600 border-red-600 hover:bg-red-50 dark:text-red-400 dark:border-red-400 dark:hover:bg-red-900/20"
                      >
                        <TrashIcon className="h-4 w-4 mr-1" />
                        Delete
                      </Button>
                    </div>
                  )}
                </div>

                {/* Article Preview */}
                {renderArticleBody(article)}

                {/* Tags/Categories - if you want to add them later */}
                <div className="mt-3 flex items-center space-x-2">
                  <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded dark:bg-blue-900/30 dark:text-blue-300">
                    {article.product}
                  </span>
                  <span className="inline-block bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded dark:bg-gray-800 dark:text-gray-300">
                    {article.customer}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination Bottom */}
        {totalPages > 1 && (
          <div className="pt-6 border-t border-border">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {first + 1} to {Math.min(first + rows, totalRecords)} of{" "}
                {totalRecords} results
              </p>
              <div className="flex space-x-1">
                <Button
                  onClick={() => onPageChangeNew(currentPage - 1)}
                  disabled={currentPage === 1}
                  variant="outline"
                  size="sm"
                >
                  <ChevronLeftIcon className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const page = currentPage <= 3 ? i + 1 : currentPage - 2 + i;
                  if (page > totalPages) return null;
                  return (
                    <Button
                      key={page}
                      onClick={() => onPageChangeNew(page)}
                      variant={page === currentPage ? "default" : "outline"}
                      size="sm"
                    >
                      {page}
                    </Button>
                  );
                })}
                <Button
                  onClick={() => onPageChangeNew(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  variant="outline"
                  size="sm"
                >
                  Next
                  <ChevronRightIcon className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingArticle} onOpenChange={(isOpen) => !isOpen && setDeletingArticle(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Are you sure you want to delete this article?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete the article.
            </DialogDescription>
          </DialogHeader>
          {deletingArticle && (
            <div className="mb-4 p-3 bg-muted rounded border border-border">
              <p className="text-sm text-foreground">
                <strong>Subject:</strong> {deletingArticle.subject}
              </p>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              onClick={handleDeleteArticle}
              disabled={deleteArticleMutation.isPending}
              variant="destructive"
            >
              {deleteArticleMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
