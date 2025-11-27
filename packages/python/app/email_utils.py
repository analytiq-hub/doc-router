import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional
from datetime import datetime
import re
import os
import sys

# Set up the path first, before other imports
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{cwd}/..")

import analytiq_data as ad

SITE_NAME = "Smart Document Router"

async def send_email(
    analytiq_client,
    to_email: str,
    from_email: str,
    subject: str,
    content: str,
) -> bool:
    """
    Send an email using AWS SES
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        content: Email content (HTML)
        from_email: Sender email address
        region_name: AWS region name (default: us-east-1)
        
    Returns:
        bool: True if email was sent successfully
        
    Raises:
        Exception: If email sending fails
    """
    try:
        # Create SES client (async)
        aws_client = await ad.aws.get_aws_client_async(analytiq_client)

        # Create email message
        message = {
            'Subject': {
                'Data': subject
            },
            'Body': {
                'Html': {
                    'Data': content
                }
            }
        }
        
        # Send email
        async with aws_client.client('ses') as ses_client:
            response = await ses_client.send_email(
                Source=from_email,
                Destination={
                    'ToAddresses': [to_email]
                },
                Message=message
            )
        
        logging.info(f"Email sent! Message ID: {response['MessageId']}")
        return True
        
    except ClientError as e:
        logging.error(f"Failed to send email: {str(e)}")
        raise Exception(f"Failed to send email: {str(e)}")

def get_verification_email_content(verification_url: str, site_url: str, user_name: Optional[str] = None) -> str:
    """
    Generate HTML content for verification email
    
    Args:
        verification_url: The URL for email verification
        site_url: The base URL of the site (for logo)
        user_name: Optional user's name for personalization
    
    Returns:
        str: HTML content for the email
    """
    greeting = f"Hello {user_name}" if user_name else "Hello"
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>{greeting},</h2>
        <p>Please verify your email address for your {SITE_NAME} account by clicking the link below:</p>
        <p style="margin: 20px 0;">
            <a href="{verification_url}" 
               style="background-color: #0070f3; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Verify Email
            </a>
        </p>
        <p>Or copy and paste this URL into your browser:</p>
        <p style="word-break: break-all; color: #666;">
            {verification_url}
        </p>
        <p>This link will expire in 24 hours.</p>
        <hr style="border: none; border-top: 1px solid #eaeaea; margin: 20px 0;">
        <p style="color: #666; font-size: 0.9em;">
            If you didn't request this verification for {SITE_NAME}, you can safely ignore this email.
        </p>
    </div>
    """

def get_email_subject(email_type: str) -> str:
    """
    Get email subject based on type
    
    Args:
        email_type: Type of the email
    
    Returns:
        str: Email subject
    """
    subjects = {
        "verification": "Verify your email address",
        "invitation": f"You've been invited to join a {SITE_NAME} organization",
        "password_reset": "Reset your password"
    }
    return subjects.get(email_type, "Notification") 

def get_invitation_email_content(
    invitation_url: str,
    site_url: str,
    expires: datetime,
    organization_name: Optional[str] = None
) -> str:
    """
    Generate HTML content for invitation email
    
    Args:
        invitation_url: The URL for accepting the invitation
        site_url: The base URL of the site
        expires: When the invitation expires
        organization_name: Optional organization name for org-specific invites
    
    Returns:
        str: HTML content for the email
    """
    expires_str = expires.strftime("%B %d, %Y at %I:%M %p UTC")
    
    # Customize message based on whether it's an org invite
    invite_message = (
        f"You've been invited to join a {SITE_NAME} organization: {organization_name}" 
        if organization_name 
        else f"You've been invited to join a {SITE_NAME} organization"
    )
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>{invite_message}</h2>
        <p>Click the button below to accept the invitation and create your account:</p>
        <p style="margin: 20px 0;">
            <a href="{invitation_url}" 
               style="background-color: #0070f3; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Accept Invitation
            </a>
        </p>
        <p>Or copy and paste this URL into your browser:</p>
        <p style="word-break: break-all; color: #666;">
            {invitation_url}
        </p>
        <p>This invitation will expire on {expires_str}.</p>
        <hr style="border: none; border-top: 1px solid #eaeaea; margin: 20px 0;">
        <p style="color: #666; font-size: 0.9em;">
            If you weren't expecting this invitation to {SITE_NAME}, you can safely ignore this email.
        </p>
    </div>
    """ 