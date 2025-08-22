"use client";

import React, { useEffect, useState } from "react";
import ArticleListTable from "@/components/ArticleListTable";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { SearchResponse } from "@/types/article";
import { toast } from "@/lib/toast";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export default function ViewArticlesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [idQuery, setIdQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(
    null
  );
  const [searchAttempted, setSearchAttempted] = useState(false);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleRefreshComplete = () => {
    setIsRefreshing(false);
    // Optional: show success message
  };

  // Initialize from URL on mount
  useEffect(() => {
    const initialId = searchParams.get("id")?.trim() || "";
    if (initialId) {
      setIdQuery(initialId);
      // Trigger the search-by-id flow programmatically
      (async () => {
        setSearchAttempted(true);
        try {
          const res = await fetch(`/api/articles/${initialId}`);
          if (!res.ok) {
            setSearchResults(null);
            toast.warning("No article found", "Try a different ID.");
            return;
          }
          const data = await res.json();
          if (!data.success || !data.data) {
            setSearchResults(null);
            toast.warning("No article found", "Try a different ID.");
            return;
          }
          const article = data.data;
          const result: SearchResponse = {
            results: [
              {
                id: article.id,
                product: article.product,
                customer: article.customer,
                subject: article.subject,
                body: article.body,
                date: article.date,
                score: 1,
              },
            ],
            total: 1,
            took: 0,
            query: initialId,
            engine: "mongodb",
          };
          setSearchResults(result);
        } catch (err) {
          setSearchResults(null);
          toast.error(
            "Search failed",
            err instanceof Error ? err.message : "Unknown error"
          );
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen">
      <Navbar currentPage="manage" />

      <div className="max-w-7xl mx-auto py-12 sm:px-8 lg:px-12">
        {/* Page Header */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">All Articles</h1>
            <p className="mt-2">View and manage all articles in the system</p>
          </div>
          <Button onClick={handleRefresh} disabled={isRefreshing}>
            {isRefreshing ? (
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Refresh
          </Button>
        </div>

        {/* Search by MongoDB _id */}
        <div className="mb-6 bg-card rounded-lg border border-border p-4">
          <div className="flex flex-col sm:flex-row gap-2 items-start sm:items-center">
            <div className="flex-1 w-full">
              <Input
                value={idQuery}
                onChange={(e) => setIdQuery(e.target.value.trim())}
                placeholder="Search by MongoDB _id (24 hex chars)"
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={async () => {
                  if (!idQuery) return;
                  setSearchAttempted(true);
                  try {
                    // Persist to URL
                    const params = new URLSearchParams(
                      Array.from(searchParams.entries())
                    );
                    params.set("id", idQuery);
                    router.replace(`${pathname}?${params.toString()}`);

                    const res = await fetch(`/api/articles/${idQuery}`);
                    if (!res.ok) {
                      setSearchResults(null);
                      toast.warning("No article found", "Try a different ID.");
                      return;
                    }
                    const data = await res.json();
                    if (!data.success || !data.data) {
                      setSearchResults(null);
                      toast.warning("No article found", "Try a different ID.");
                      return;
                    }
                    const article = data.data;
                    const result: SearchResponse = {
                      results: [
                        {
                          id: article.id,
                          product: article.product,
                          customer: article.customer,
                          subject: article.subject,
                          body: article.body,
                          date: article.date,
                          score: 1,
                        },
                      ],
                      total: 1,
                      took: 0,
                      query: idQuery,
                      engine: "mongodb",
                    };
                    setSearchResults(result);
                  } catch (err) {
                    setSearchResults(null);
                    toast.error(
                      "Search failed",
                      err instanceof Error ? err.message : "Unknown error"
                    );
                  }
                }}
                disabled={!idQuery}
              >
                Search by ID
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setIdQuery("");
                  setSearchResults(null);
                  setSearchAttempted(false);
                  const params = new URLSearchParams(
                    Array.from(searchParams.entries())
                  );
                  params.delete("id");
                  router.replace(
                    params.toString()
                      ? `${pathname}?${params.toString()}`
                      : pathname
                  );
                }}
                disabled={!idQuery && !searchResults}
              >
                Clear
              </Button>
            </div>
          </div>
        </div>

        {/* Article List */}
        <ArticleListTable
          isSearchView={!!searchResults}
          searchResults={searchResults || undefined}
          searchAttempted={searchAttempted}
          refreshTrigger={refreshTrigger}
          onRefreshComplete={handleRefreshComplete}
          showActions
        />
      </div>
    </div>
  );
}
