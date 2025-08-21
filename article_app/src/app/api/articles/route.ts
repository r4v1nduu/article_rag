import { NextRequest, NextResponse } from "next/server";
import { articleService } from "@/lib/articleService";
import { createArticleSchema } from "@/lib/validation";
import { ArticleCreate } from "@/types/article";

// Optimized cache headers for maximum performance
const CACHE_HEADERS = {
  "Cache-Control": "public, s-maxage=30, stale-while-revalidate=300",
  "CDN-Cache-Control": "public, s-maxage=30",
  "Vercel-CDN-Cache-Control": "public, s-maxage=30",
  "X-Content-Type-Options": "nosniff",
};

// GET /api/articles - List articles with pagination (optimized)
export async function GET(request: NextRequest) {
  const startTime = Date.now();

  try {
    const { searchParams } = new URL(request.url);
    const skip = Math.max(0, parseInt(searchParams.get("skip") || "0"));
    const limit = Math.min(
      100,
      Math.max(1, parseInt(searchParams.get("limit") || "20"))
    ); // Default to 20 for faster loads

    const result = await articleService.getArticles(skip, limit);

    const responseTime = Date.now() - startTime;

    return NextResponse.json(
      {
        success: true,
        data: result.articles,
        total: result.total,
        skip,
        limit,
        meta: {
          responseTime,
          hasMore: skip + limit < result.total,
        },
      },
      {
        headers: {
          ...CACHE_HEADERS,
        },
      }
    );
  } catch (error) {
    console.error("Error fetching articles:", error);

    // Check if it's a database connection error
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    const isConnectionError = errorMessage.includes("MONGODB_URI") || 
                             errorMessage.includes("environment variable") ||
                             errorMessage.includes("ECONNREFUSED");

    return NextResponse.json(
      {
        success: false,
        error: isConnectionError 
          ? "Database connection failed. Please check your environment configuration."
          : "Service temporarily unavailable. Please try again later.",
        code: isConnectionError ? "DATABASE_CONNECTION_ERROR" : "SERVICE_UNAVAILABLE",
        details: isConnectionError ? errorMessage : undefined
      },
      { status: isConnectionError ? 500 : 503 }
    );
  }
}

// POST /api/articles - Create a new article (optimized)
export async function POST(request: NextRequest) {
  const startTime = Date.now();

  try {
    const body = await request.json();

    const validationResult = createArticleSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          success: false,
          error: "Invalid input provided.",
          code: "VALIDATION_ERROR",
          details: validationResult.error.flatten(),
        },
        { status: 400 }
      );
    }

    const articleData: ArticleCreate = validationResult.data;

    try {
      const article = await articleService.createArticle(articleData);
      const responseTime = Date.now() - startTime;

      return NextResponse.json(
        {
          success: true,
          data: article,
          meta: { responseTime },
        },
        {
          status: 201,
          headers: {
            Location: `/api/articles/${article.id}`,
          },
        }
      );
    } catch (dbError) {
      console.error("Error creating article:", dbError);

      const responseTime = Date.now() - startTime;
      return NextResponse.json(
        {
          success: false,
          error: "Service temporarily unavailable. Could not save article.",
          code: "SERVICE_UNAVAILABLE",
          meta: { responseTime },
        },
        { status: 503 }
      );
    }
  } catch (error) {
    console.error("Error in POST /api/articles:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Invalid request format",
        code: "INVALID_REQUEST",
      },
      { status: 400 }
    );
  }
}
