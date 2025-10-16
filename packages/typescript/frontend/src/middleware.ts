import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token;
    const path = req.nextUrl.pathname;

    // Admin-only routes - comment in.
    if (path.startsWith("/settings/account")) {
      if (token?.role !== "admin") {
        return NextResponse.redirect(new URL("/settings", req.url));
      }
    }

    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token }) => !!token
    },
  }
);

export const config = {
  matcher: [
    // Only protect these specific routes
    "/settings/:path*",
    "/orgs/:path*",
  ]
};