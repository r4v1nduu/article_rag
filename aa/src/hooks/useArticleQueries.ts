import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiService } from "@/services/api";
import { Article, ArticleCreate, ArticleUpdate, SearchRequest } from "@/types/article";

// Query keys for better cache management
export const articleKeys = {
  all: ["articles"] as const,
  lists: () => [...articleKeys.all, "list"] as const,
  list: (skip: number, limit: number) =>
    [...articleKeys.lists(), { skip, limit }] as const,
  searches: () => [...articleKeys.all, "search"] as const,
  search: (query: string, size: number) =>
    [...articleKeys.searches(), { query, size }] as const,
};

// Optimized hook for fetching articles with pagination
export function useArticles(skip: number = 0, limit: number = 20) {
  // Reduced default limit for faster loads
  return useQuery({
    queryKey: articleKeys.list(skip, limit),
    queryFn: () => apiService.getArticles(skip, limit),
    staleTime: 1 * 60 * 1000, // 1 minute - shorter for fresher data
    gcTime: 5 * 60 * 1000, // 5 minutes garbage collection
    placeholderData: (
      previousData: { data: Article[]; total: number } | undefined
    ) => previousData, // Keep previous data while loading
    refetchOnWindowFocus: false, // Disable refetch on window focus for better performance
  });
}

// Optimized hook for searching articles
export function useArticleSearch(
  searchRequest: SearchRequest,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: articleKeys.search(searchRequest.q, searchRequest.size || 20), // Reduced default
    queryFn: () => apiService.searchArticles(searchRequest),
    enabled: enabled && !!searchRequest.q.trim(),
    staleTime: 3 * 60 * 1000, // 3 minutes for search results
    gcTime: 10 * 60 * 1000, // 10 minutes garbage collection
    refetchOnWindowFocus: false, // Disable for search results
  });
}

// Optimized mutation for creating articles
export function useCreateArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (articleData: ArticleCreate) => apiService.createArticle(articleData),
    onSuccess: (newArticle: Article) => {
      // Invalidate and refetch article lists
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() });

      // Optimistically add to cache if we have the first page
      const firstPageKey = articleKeys.list(0, 10);
      queryClient.setQueryData(firstPageKey, (oldData: unknown) => {
        const data = oldData as { data?: Article[]; total?: number } | undefined;
        if (data?.data) {
          return {
            ...data,
            data: [newArticle, ...data.data.slice(0, 9)], // Add new article to top, remove last
            total: (data.total || 0) + 1,
          };
        }
        return oldData;
      });
    },
  });
}

// Optimized mutation for updating articles
export function useUpdateArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ArticleUpdate }) =>
      apiService.updateArticle(id, data),
    onSuccess: (
      updatedArticle: Article,
      { id }: { id: string; data: ArticleUpdate }
    ) => {
      // Update article in all list queries
      queryClient.setQueriesData(
        { queryKey: articleKeys.lists(), exact: false },
        (oldData: unknown) => {
          const data = oldData as { data?: Article[] } | undefined;
          if (data?.data) {
            return {
              ...data,
              data: data.data.map((article: Article) =>
                article.id === id ? updatedArticle : article
              ),
            };
          }
          return oldData;
        }
      );

      // Invalidate search queries as they might be affected
      queryClient.invalidateQueries({ queryKey: articleKeys.searches() });
    },
  });
}

// Optimized mutation for deleting articles
export function useDeleteArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiService.deleteArticle(id),
    onSuccess: (_: void, deletedId: string) => {
      // Remove from all list queries
      queryClient.setQueriesData(
        { queryKey: articleKeys.lists(), exact: false },
        (oldData: unknown) => {
          const data = oldData as
            | { data?: Article[]; total?: number }
            | undefined;
          if (data?.data) {
            return {
              ...data,
              data: data.data.filter((article: Article) => article.id !== deletedId),
              total: Math.max(0, (data.total || 1) - 1),
            };
          }
          return oldData;
        }
      );

      // Invalidate search queries
      queryClient.invalidateQueries({ queryKey: articleKeys.searches() });
    },
  });
}
