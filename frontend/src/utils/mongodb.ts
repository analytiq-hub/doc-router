// This approach is taken from https://github.com/vercel/next.js/tree/canary/examples/with-mongodb
import { MongoClient } from "mongodb"
 
const env = process.env.ENV || "dev"
// console.log(`ENV: ${env}`)

const mongodbUri = process.env.MONGODB_URI || "mongodb://localhost:27017"

// Parse the URI to handle authentication and database name correctly
// For authenticated connections, we need to insert the database name after the host/port but before query params
let uri: string
if (mongodbUri.includes('@') && mongodbUri.includes('?')) {
  // Authenticated connection with query params: mongodb://user:pass@host:port/?authSource=admin
  // Check if there's already a trailing slash before the query params
  const beforeQuery = mongodbUri.split('?')[0]
  const queryParams = mongodbUri.split('?')[1]
  const separator = beforeQuery.endsWith('/') ? '' : '/'
  uri = `${beforeQuery}${separator}${env}?${queryParams}`
} else if (mongodbUri.includes('@') && !mongodbUri.includes('?')) {
  // Authenticated connection without query params: mongodb://user:pass@host:port
  const separator = mongodbUri.endsWith('/') ? '' : '/'
  uri = `${mongodbUri}${separator}${env}`
} else if (!mongodbUri.includes('@') && mongodbUri.includes('?')) {
  // Non-authenticated connection with query params: mongodb://host:port/?param=value
  const beforeQuery = mongodbUri.split('?')[0]
  const queryParams = mongodbUri.split('?')[1]
  const separator = beforeQuery.endsWith('/') ? '' : '/'
  uri = `${beforeQuery}${separator}${env}?${queryParams}`
} else {
  // Non-authenticated connection without query params: mongodb://host:port
  const separator = mongodbUri.endsWith('/') ? '' : '/'
  uri = `${mongodbUri}${separator}${env}`
}

// console.log(`MONGODB_URI: ${mongodbUri}`)
// console.log(`ENV: ${env}`)
// console.log(`Final URI: ${uri}`)

const options = {}
 
let mongoClient: MongoClient
 
if (process.env.NODE_ENV === "development") {
  // In development mode, use a global variable so that the value
  // is preserved across module reloads caused by HMR (Hot Module Replacement).
  const globalWithMongo = global as typeof globalThis & {
    _mongoClient?: MongoClient
  }
 
  if (!globalWithMongo._mongoClient) {
    globalWithMongo._mongoClient = new MongoClient(uri, options)
  }
  mongoClient = globalWithMongo._mongoClient
} else {
  // In production mode, it's best to not use a global variable.
  mongoClient = new MongoClient(uri, options)
}

// Function to get the database with the correct name
export function getDatabase() {
  return mongoClient.db(env)
}
 
// Export a module-scoped MongoClient. By doing this in a
// separate module, the client can be shared across functions.
export default mongoClient
