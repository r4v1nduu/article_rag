import {
  Article,
  ArticleCreate,
  ArticleUpdate,
  SearchRequest,
  SearchResponse,
} from "@/types/article";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

class ApiService {
  private async fetchWithError(url: string, options?: RequestInit) {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.error || `HTTP error! status: ${response.status}`
      );
    }

    return response.json();
  }

  // Get articles with pagination
  async getArticles(
    skip: number = 0,
    limit: number = 50
  ): Promise<{ data: Article[]; total: number }> {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
    });

    const result = await this.fetchWithError(
      `${API_BASE_URL}/api/articles?${params}`
    );
    return {
      data: result.data,
      total: result.total,
    };
  }

  // Create a new article
  async createArticle(article: ArticleCreate): Promise<Article> {
    const result = await this.fetchWithError(`${API_BASE_URL}/api/articles`, {
      method: "POST",
      body: JSON.stringify(article),
    });
    return result.data;
  }

  // Update an article
  async updateArticle(id: string, article: ArticleUpdate): Promise<Article> {
    const result = await this.fetchWithError(
      `${API_BASE_URL}/api/articles/${id}`,
      {
        method: "PUT",
        body: JSON.stringify(article),
      }
    );
    return result.data;
  }

  // Delete an article
  async deleteArticle(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/articles/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }
    // No JSON parsing on 204/empty responses
  }

  // Search articles
  async searchArticles(request: SearchRequest): Promise<SearchResponse> {
    const params = new URLSearchParams({
      q: request.q,
      size: (request.size || 50).toString(),
    });

    const result = await this.fetchWithError(
      `${API_BASE_URL}/api/articles/search?${params}`
    );
    return result.data;
  }
}

export const apiService = new ApiService();
export default apiService;
