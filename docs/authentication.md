# Authentication Support

* On initial install, the admin user is created from the following environment variables:
  * `ADMIN_EMAIL`
  * `ADMIN_PASSWORD`
  * See the example `.env` files for more details
* We support Google OAuth2.0 and GitHub OAuth2.0, as well as email/password authentication
  * Registration and email verification are handled by FastAPI (`POST /v0/account/auth/register`, verification emails)
* Browser sessions use an HS256 JWT minted by FastAPI after login or OAuth (`packages/python/app/session_jwt.py`)
  * The Next.js server stores the JWT in an httpOnly cookie and verifies it with `NEXTAUTH_SECRET` (`packages/typescript/frontend/src/utils/sessionFromToken.ts`)
  * API requests send the same JWT as `Authorization: Bearer …`
* Platform OAuth credentials: `AUTH_GOOGLE_*`, `AUTH_GITHUB_*` (FastAPI `account_auth` routes)
* We use MongoDB as the backend database
  * Users are stored in the `users` collection
  * Linked OAuth provider rows are stored in the `accounts` collection

# FAQ

* How do I deal with a `OAuthAccountNotLinked` Error with OAuth providers?
  * This occurs when the same email was used to log in through a different OAuth provider, or through email/password authentication.
  * To resolve, log in through the old provider, and delete the user through our settings page.
* If the error persists:
  * An older version of the code was inconsistently saving OAuth information to the database. As of version 6.0.2, this is fixed.
  * To further resolve this, ask the admin to delete the user/account records in the `users` and `accounts` collections. Then, re-authenticate with the OAuth provider.
