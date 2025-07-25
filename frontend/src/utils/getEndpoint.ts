/**
 * Get the proper API endpoint based on the environment.
 */
export default function getEndpoint() {
  const env = process.env.NODE_ENV || "development";
  switch (env) {
    case "development":
      return "http://localhost:5050";
    case "production":
      // throw new Error("Not yet supported")
      // For a FOUC test I am doing
      return "http://localhost:5050"; // Replace with the production URL when ready
    default:
      return "http://localhost:5000";
  }
}
