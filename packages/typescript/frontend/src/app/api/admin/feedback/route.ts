import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/auth';
import clientPromise from '@/utils/mongodb';

// Add this export to mark the route as dynamic
export const dynamic = 'force-dynamic';

export async function GET() {
    
  try {
    const session = await getServerSession(authOptions);
    
    // Debug the session object to see what's available
    console.log("[NEXTJS] Complete Session:", JSON.stringify(session, null, 2));
    
    const isAdmin = (session?.user as { isSysadmin?: boolean } | undefined)?.isSysadmin === true;

    if (!session || !isAdmin) {
      console.log("[NEXTJS] Auth check failed - Session exists:", !!session, "Sysadmin:", isAdmin);
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 403 }
      );
    }
    
    // Connect to database
    const client = await clientPromise;
    const db = client.db();
    
    // Fetch feedback entries, sorted by creation date (newest first)
    const feedbackEntries = await db.collection('feedback')
      .find({})
      .sort({ createdAt: -1 })
      .toArray();
    
    return NextResponse.json(
      { feedback: feedbackEntries },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error fetching feedback:', error);
    return NextResponse.json(
      { error: 'Failed to fetch feedback' },
      { status: 500 }
    );
  }
}