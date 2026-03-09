import axios from 'axios';
import NextAuth, { NextAuthOptions, Session } from "next-auth"
import { MongoDBAdapter } from "@auth/mongodb-adapter"
import mongoClient, { getDatabase } from "@/utils/mongodb"
import { Adapter } from "next-auth/adapters"
import type { Account, DefaultUser } from "next-auth"
import crypto from 'crypto';

import GithubProvider from "next-auth/providers/github";
import GoogleProvider from "next-auth/providers/google";
import { JWT } from "next-auth/jwt";
import { AppSession } from '@/types/AppSession';
import CredentialsProvider from "next-auth/providers/credentials";
import { compare } from "bcryptjs";

interface CustomUser extends DefaultUser {
    emailVerified?: Date | null;
}

/**
 * Create HMAC signature for request authentication
 * Uses NEXTAUTH_SECRET to sign the raw JSON string
 */
function createRequestSignature(jsonString: string): string {
    const secret = process.env.NEXTAUTH_SECRET;
    if (!secret) {
        throw new Error('NEXTAUTH_SECRET is not configured');
    }

    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(jsonString);
    return hmac.digest('hex');
}

const customAdapter = MongoDBAdapter(mongoClient) as Adapter

export const authOptions: NextAuthOptions = {
    session: {
        strategy: 'jwt' as const,
    },
    adapter: customAdapter,
    secret: process.env.NEXTAUTH_SECRET ?? "",
    providers: [
        CredentialsProvider({
            name: "Credentials",
            credentials: {
                email: { label: "Email", type: "email" },
                password: { label: "Password", type: "password" }
            },
            async authorize(credentials) {
                if (!credentials?.email || !credentials?.password) {
                    throw new Error("Missing credentials");
                }

                try {
                    const db = getDatabase();
                    const user = await db.collection("users").findOne({ 
                        email: credentials.email 
                    });

                    if (!user || !user.password) {
                        throw new Error("No user found with this email");
                    }

                    // Check email verification status
                    if (!user.email_verified) {
                        throw new Error("Please verify your email before logging in");
                    }

                    const isValid = await compare(credentials.password, user.password);
                    
                    if (!isValid) {
                        throw new Error("Invalid password");
                    }

                    return {
                        id: user._id.toString(),
                        email: user.email,
                        name: user.name,
                        role: user.role || "user"
                    };
                } catch (error) {
                    console.error("Auth error:", error);
                    throw error;
                }
            }
        }),
        GithubProvider({
            clientId: process.env.AUTH_GITHUB_ID ?? "", // ?? only considers null or undefined as false
            clientSecret: process.env.AUTH_GITHUB_SECRET ?? "",
        }),
        GoogleProvider({
            clientId: process.env.AUTH_GOOGLE_ID ?? "",
            clientSecret: process.env.AUTH_GOOGLE_SECRET ?? "",
            authorization: {
                params: {
                    prompt: "consent",
                    access_type: "offline",
                    response_type: "code",
                    scope: "openid email profile"
                }
            }
        })
    ],
    callbacks: {
        async signIn({ user, account }: { user: CustomUser, account: Account | null }) {
            try {
                if (account?.provider === 'google' || account?.provider === 'github') {
                    // Call FastAPI to handle user/account/org creation and Stripe sync
                    const apiUrl = process.env.FASTAPI_BACKEND_URL || 'http://backend:8000';
                    const payload = {
                        email: user.email,
                        name: user.name,
                        email_verified: user.emailVerified ?? false,
                        provider: account.provider,
                        provider_account_id: account.providerAccountId,
                        account: {
                            type: account.type,
                            access_token: account.access_token,
                            expires_at: account.expires_at,
                            token_type: account.token_type,
                            scope: account.scope,
                            id_token: account.id_token,
                            refresh_token: account.refresh_token
                        }
                    };
                    const payloadJson = JSON.stringify(payload);
                    const signature = createRequestSignature(payloadJson);

                    const response = await axios.post(`${apiUrl}/v0/account/auth/oauth`, payloadJson, {
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Request-Signature': signature
                        }
                    });

                    console.log(`OAuth sign-in processed: ${response.data.is_new_user ? 'new' : 'existing'} user ${response.data.user_id}`);
                }
                return true;
            } catch (error) {
                console.error("OAuth sign-in error:", error);
                return false;
            }
        },
        async jwt({ token, account, profile, trigger, session, user }) {
            if (user) {
                token.id = user.id;
                token.role = user.role;
                
                // Only get new FastAPI token on initial sign-in
                try {
                    const apiUrl = process.env.FASTAPI_BACKEND_URL || 'http://backend:8000';
                    const payload = {
                        id: user.id,
                        name: user.name,
                        email: user.email
                    };
                    const payloadJson = JSON.stringify(payload);
                    const signature = createRequestSignature(payloadJson);

                    const response = await axios.post(`${apiUrl}/v0/account/auth/token`, payloadJson, {
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Request-Signature': signature
                        }
                    });
                    token.apiAccessToken = response.data.token;
                } catch (error) {
                    console.error('Error getting initial API token:', error);
                }
            }

            // If name is being updated, update the token
            if (trigger === "update" && session?.user?.name) {
                token.name = session.user.name;
            }

            // Persist the OAuth access_token to the token right after signin
            if (account) {
                token.providerAccessToken = account.access_token;
                
                // For Google, use email as a stable identifier
                if (account.provider === 'google' && profile?.email) {
                    token.sub = profile.email;
                }
            }

            //console.log('Token in auth.ts:', token);

            return token;
        },
        async session({ session, token }: { 
            session: Session; 
            token: JWT; 
            trigger?: "update" | undefined;
        }) {
            // Cast the session to AppSession to add our custom properties
            const appSession = session as AppSession;
            appSession.user.id = token.id;
            appSession.user.role = token.role;
            appSession.providerAccessToken = token.providerAccessToken as string;
            appSession.apiAccessToken = token.apiAccessToken as string;
            appSession.expires = session.expires;
            
            if (session.user && token.name) {
                session.user.name = token.name;
            }
            
            return appSession;
        },
        async redirect({ baseUrl }) {
            // Default to homepage for safety
            return baseUrl;
        },
    },
    pages: {
        signIn: '/auth/signin',
        //signOut: '/auth/signout',
        //error: '/auth/error',
        //verifyRequest: '/auth/verify-request',
        //newUser: '/auth/new-user'
    },
};

export const handlers = NextAuth(authOptions);