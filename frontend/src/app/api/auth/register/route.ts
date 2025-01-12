import { NextResponse } from 'next/server';
import mongoClient from '@/utils/mongodb';
import { hash } from 'bcryptjs';

export async function POST(req: Request) {
    try {
        const { email, password, name, organizationName, organizationType } = await req.json();
        
        if (!organizationName || !organizationType || !['team', 'enterprise'].includes(organizationType)) {
            return NextResponse.json(
                { error: 'Organization name and valid type (team/enterprise) are required' },
                { status: 400 }
            );
        }

        const db = mongoClient.db();

        // Check if user exists
        const existingUser = await db.collection('users').findOne({ email });
        if (existingUser) {
            return NextResponse.json(
                { error: 'User already exists' },
                { status: 400 }
            );
        }

        // Create new user
        const hashedPassword = await hash(password, 12);
        const result = await db.collection('users').insertOne({
            email,
            password: hashedPassword,
            name,
            role: 'user',
            emailVerified: false,
            createdAt: new Date(),
        });

        // Create organization
        const organization = {
            name: organizationName,
            type: organizationType,
            members: [{
                user_id: result.insertedId.toString(),
                role: "admin"
            }],
            created_at: new Date(),
            updated_at: new Date()
        };

        await db.collection("organizations").insertOne(organization);

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Registration error:', error);
        return NextResponse.json(
            { error: 'Registration failed' },
            { status: 500 }
        );
    }
}
