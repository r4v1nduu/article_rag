import { ObjectId } from "mongodb";
import { getArticlesCollection } from "../lib/database";
import type {
  Article,
  ArticleCreate,
  ArticleUpdate,
  SearchResult,
  SearchResponse,
} from "@/types/article";

// MongoDB document interface
interface ArticleDocument {
  _id: ObjectId;
  product: string;
  customer: string;
  subject: string;
  body: string;
  date: string;
  created_at?: Date;
  updated_at?: Date;
}

export class ArticleService {
  // Create a new article
  async createArticle(articleData: ArticleCreate): Promise<Article> {
    const collection = await getArticlesCollection();

    const articleDoc = {
      ...articleData,
      created_at: new Date(),
      updated_at: new Date(),
    };

    const result = await collection.insertOne(articleDoc);

    // Retrieve the created article
    const createdArticle = await collection.findOne({ _id: result.insertedId });

    if (createdArticle) {
      return this._mapDocumentToArticle(createdArticle as ArticleDocument);
    }

    throw new Error("Failed to create article");
  }

  private _mapDocumentToArticle(article: ArticleDocument): Article {
    return {
      id: article._id.toString(),
      product: article.product,
      customer: article.customer,
      subject: article.subject,
      body: article.body,
      date: article.date,
      created_at: article.created_at?.toISOString(),
      updated_at: article.updated_at?.toISOString(),
    };
  }

  // Get a single article by ID
  async getArticle(articleId: string): Promise<Article | null> {
    if (!ObjectId.isValid(articleId)) {
      return null;
    }

    const collection = await getArticlesCollection();
    const article = await collection.findOne({ _id: new ObjectId(articleId) });

    if (article) {
      return this._mapDocumentToArticle(article as ArticleDocument);
    }

    return null;
  }

  // Get articles with pagination
  async getArticles(
    skip: number = 0,
    limit: number = 50
  ): Promise<{ articles: Article[]; total: number }> {
    const collection = await getArticlesCollection();

    // Ensure index exists for sorting
    await collection.createIndex({ date: -1 });

    // Get total count
    const total = await collection.countDocuments({});

    // Get articles with pagination
    const cursor = collection
      .find({})
      .skip(skip)
      .limit(limit)
      .sort({ date: -1 });
    const articles: Article[] = [];

    await cursor.forEach((article) => {
      articles.push(this._mapDocumentToArticle(article as ArticleDocument));
    });

    return { articles, total };
  }

  // Update an article
  async updateArticle(
    articleId: string,
    articleUpdate: ArticleUpdate
  ): Promise<Article | null> {
    if (!ObjectId.isValid(articleId)) {
      return null;
    }

    const collection = await getArticlesCollection();
    const updateData = {
      ...articleUpdate,
      updated_at: new Date(),
    };

    const result = await collection.updateOne(
      { _id: new ObjectId(articleId) },
      { $set: updateData }
    );

    if (result.modifiedCount > 0) {
      const updatedArticle = await collection.findOne({
        _id: new ObjectId(articleId),
      });
      if (updatedArticle) {
        return this._mapDocumentToArticle(updatedArticle as ArticleDocument);
      }
    }

    return null;
  }

  // Delete an article
  async deleteArticle(articleId: string): Promise<boolean> {
    if (!ObjectId.isValid(articleId)) {
      return false;
    }

    const collection = await getArticlesCollection();
    const result = await collection.deleteOne({ _id: new ObjectId(articleId) });

    return result.deletedCount > 0;
  }

  // Search articles using MongoDB
  async searchArticles(
    query: string,
    size: number = 50
  ): Promise<SearchResponse> {
    return await this.searchWithMongoDB(query, size);
  }

  // MongoDB search implementation
  private async searchWithMongoDB(
    query: string,
    size: number
  ): Promise<SearchResponse> {
    const collection = await getArticlesCollection();

    // Perform MongoDB text search
    const cursor = collection
      .find(
        { $text: { $search: query } },
        { projection: { score: { $meta: "textScore" } } }
      )
      .sort({ score: { $meta: "textScore" }, date: -1 })
      .limit(size);

    const results: SearchResult[] = [];
    await cursor.forEach((doc) => {
      const articleDoc = doc as ArticleDocument;
      results.push({
        id: articleDoc._id.toString(),
        product: articleDoc.product,
        customer: articleDoc.customer,
        subject: articleDoc.subject,
        body: articleDoc.body,
        date: articleDoc.date,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        score: (doc as any).score || 1.0,
      });
    });

    return {
      results,
      total: results.length,
      took: 0, // MongoDB doesn't provide timing info
      query,
      engine: "mongodb",
    };
  }
}

// Create and export service instance
export const articleService = new ArticleService();
