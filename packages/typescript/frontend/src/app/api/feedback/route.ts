import { NextRequest, NextResponse } from 'next/server';
import { getAppServerSession } from '@/utils/session';
import { getDatabase } from '@/utils/mongodb';

export async function POST(req: NextRequest) {
  try {
    const session = await getAppServerSession();
    
    // Check if user is authenticated
    if (!session) {
      return NextResponse.json(
        { error: 'You must be signed in to submit feedback' },
        { status: 401 }
      );
    }
    
    // Parse request body
    const { feedback, userId, userName, createdAt } = await req.json();
    
    // Validate required fields
    if (!feedback || typeof feedback !== 'string') {
      return NextResponse.json(
        { error: 'Feedback is required' },
        { status: 400 }
      );
    }
    
    // Connect to database
    const db = getDatabase();
    
    // Create feedback document with email hard-coded from session
    const feedbackDoc = {
      content: feedback,
      email: session.user.email || null, // Hard-coded to user's login email
      userId: userId || session.user.id || null,
      userName: userName || session.user.name || null,
      createdAt: createdAt || new Date().toISOString(),
      status: 'new',
    };
    
    // Insert feedback into database
    await db.collection('feedback').insertOne(feedbackDoc);
    
    return NextResponse.json(
      { success: true, message: 'Feedback submitted successfully' },
      { status: 201 }
    );
  } catch (error) {
    console.error('Error submitting feedback:', error);
    return NextResponse.json(
      { error: 'Failed to submit feedback' },
      { status: 500 }
    );
  }
} 