import { MongoClient, Db, Collection, ReadPreference } from "mongodb";

// Configuration from environment variables
const MONGODB_URI = process.env.MONGODB_URI;
const DATABASE_NAME = process.env.DATABASE_NAME;
const COLLECTION_NAME = process.env.COLLECTION_NAME;

// Check environment variables and log warnings instead of throwing immediately
const checkEnvironmentVariables = () => {
  const missingVars = [];
  if (!MONGODB_URI) missingVars.push("MONGODB_URI");
  if (!DATABASE_NAME) missingVars.push("DATABASE_NAME");
  if (!COLLECTION_NAME) missingVars.push("COLLECTION_NAME");
  
  if (missingVars.length > 0) {
    console.warn(`⚠️ Missing environment variables: ${missingVars.join(", ")}`);
    console.warn("Please create a .env.local file with the required variables");
  }
  
  return missingVars.length === 0;
};

const hasRequiredEnvVars = checkEnvironmentVariables();

// Global variables for connection reuse
let mongoClient: MongoClient | null = null;
let db: Db | null = null;

// MongoDB Connection with optimized settings
export async function connectToMongo(): Promise<Db> {
  if (!hasRequiredEnvVars) {
    throw new Error("Missing required environment variables for database connection");
  }
  
  if (!mongoClient || !db) {
    try {
      // Try with compression first
      let connectionOptions: {
        maxPoolSize: number;
        minPoolSize: number;
        maxIdleTimeMS: number;
        serverSelectionTimeoutMS: number;
        socketTimeoutMS: number;
        heartbeatFrequencyMS: number;
        compressors?: ("zstd" | "zlib" | "none" | "snappy")[];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        readPreference: any;
      } = {
        // Optimized connection settings
        maxPoolSize: 20, // Increased pool size for better performance
        minPoolSize: 5,
        maxIdleTimeMS: 30000,
        serverSelectionTimeoutMS: 5000, // Faster timeout
        socketTimeoutMS: 20000,
        heartbeatFrequencyMS: 10000,
        // Connection optimization
        compressors: ["zstd", "zlib"], // Enable compression for better network performance
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        readPreference: ReadPreference.SECONDARY_PREFERRED as any,
      };

      try {
        mongoClient = new MongoClient(MONGODB_URI!, connectionOptions);
        await mongoClient.connect();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } catch (compressionError: any) {
        // Fallback without compression if compression fails
        console.warn(
          "⚠️ Compression failed, connecting without compression:",
          compressionError?.message || compressionError
        );
        if (mongoClient) {
          await mongoClient.close();
        }

        connectionOptions = {
          maxPoolSize: 20,
          minPoolSize: 5,
          maxIdleTimeMS: 30000,
          serverSelectionTimeoutMS: 5000,
          socketTimeoutMS: 20000,
          heartbeatFrequencyMS: 10000,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          readPreference: ReadPreference.SECONDARY_PREFERRED as any,
        };

        mongoClient = new MongoClient(MONGODB_URI!, connectionOptions);
        await mongoClient.connect();
      }

      db = mongoClient.db(DATABASE_NAME);
      console.log(`✅ Connected to MongoDB: ${DATABASE_NAME}`);
    } catch (error) {
      console.error("❌ Failed to connect to MongoDB:", error);
      throw error;
    }
  }
  return db;
}

// Get MongoDB collection
export async function getArticlesCollection(): Promise<Collection> {
  const db = await connectToMongo();
  return db.collection(COLLECTION_NAME!);
}

export async function getCustomersCollection(): Promise<Collection> {
  const db = await connectToMongo();
  return db.collection("customers");
}

export async function getProductsCollection(): Promise<Collection> {
  const db = await connectToMongo();
  return db.collection("products");
}

// Database cleanup (for graceful shutdown)
export async function closeDatabaseConnections(): Promise<void> {
  if (mongoClient) {
    await mongoClient.close();
    mongoClient = null;
    db = null;
    console.log("✅ Disconnected from MongoDB");
  }
}

export { COLLECTION_NAME };
