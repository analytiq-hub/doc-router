import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";
import type { NextRequestWithAuth } from "next-auth/middleware";
import type { JWT } from "next-auth/jwt";

export default withAuth(
  function proxy(req: NextRequestWithAuth) {
    const token = req.nextauth.token as (JWT & { role?: string }) | null;
    const path = req.nextUrl.pathname;

    // Admin-only routes
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
