# Email Campaign Plan for DocRouter

## Overview

This document outlines two email campaigns:
1. **Onboarding Campaign** - For users who have registered an account
2. **Prospect Campaign** - For potential users who might be interested in DocRouter

---

## Campaign 1: Onboarding Campaign (Registered Users)

### Goal
Guide new users through their first steps: upload documents, tailor prompts, see results, then learn about schemas and workflows.

### Target Audience
Users who have successfully registered and verified their email address.

### Email Sequence

#### Email 1: Upload, Tailor, See Results (Day 0 - Immediate)
**Trigger:** User completes email verification

**Purpose:** Get users to their first successful extraction quickly - upload documents, create/tailor a prompt, and see results.

**Content:**
- Welcome message
- Quick start: Upload documents → Create/Tailor prompt → See results
- Brief overview of the process
- Links to in-depth resources (schemas, REST API, workflows, Claude Code)

**Key Sections (with alternating background colors):**

**Section 1 (White background):**
- Personal greeting: "{{ contact.FIRSTNAME | default: 'there' }}, welcome to DocRouter! Let's get you extracting data from your first document."
- Introduction: "The fastest way to see DocRouter in action is to upload a document, create a prompt, and see the results. Here's how to get started in three simple steps."
- Primary CTA: "Upload Your First Document"

**Section 2 (Light colored background - e.g., #f8f9fa):**
- "Get started in 3 steps" headline
- Step-by-step guide:
  1. **Upload documents** - Drag & drop or browse files (PDFs, images, Word, Excel, etc.)
  2. **Tailor your prompt** - Write clear instructions about what data to extract
  3. **See results** - Review AI-extracted data and verify accuracy
- Brief explanation: "Once you see your first extraction, you'll understand how DocRouter works. Then you can refine prompts and explore advanced features."

**Section 3 (White background):**
- "Learn more (in-depth)" headline
- Brief descriptions with links:
  - **Schemas** - Define structured output formats for consistent data extraction → [Learn about schemas]({{ params.site_url }}/docs/knowledge_base/schemas)
  - **REST API** - Integrate DocRouter into your workflows programmatically → [API Documentation]({{ params.site_url }}/docs/api)
  - **Workflows** - Automate document processing with N8N and Temporal → [Workflow Guide]({{ params.site_url }}/docs/workflows)
  - **Claude Code** - Use Claude Code to create schemas and configure prompts → [Claude Code Guide]({{ params.site_url }}/docs/claude-code)
- Brief explanation: "These resources will help you go deeper once you've seen your first results."

**Section 4 (Light colored background):**
- "Need a hand?" headline
- Support message: "We're here to help. If you have questions, our support team is just a click away."
- CTA: "Contact Support"

**Subject Line:**
"Upload, tailor, see results - Get started in 3 steps 📄"

**Preview Text:**
Welcome to DocRouter! Upload a document, create a prompt, and see your first extraction in minutes.

---

#### Email 2: Learn About Schemas (Day 3)
**Trigger:** 3 days after registration (or if user has uploaded documents and created prompts)

**Purpose:** Deep dive into schemas - what they are, why they matter, and how to use them effectively.

**Content:**
- What are schemas and why they matter
- How to create schemas
- Linking schemas to prompts
- Best practices for schema design
- Optional: How Claude Code can be used to create schemas and configure prompts
- Brief links to: REST API, workflows, Claude Code

**Key Sections (with alternating background colors):**

**Section 1 (White background):**
- Personal greeting: "{{ contact.FIRSTNAME | default: 'there' }}, now that you've seen DocRouter extract data, let's talk about schemas."
- Introduction: "Schemas define the structure of your extracted data. They ensure consistency, validate output, and make your data easier to work with. Let's explore how to use them effectively."
- Primary CTA: "Create Your First Schema"

**Section 2 (Light colored background):**
- "What are schemas?" headline
- Explanation: "Schemas are JSON Schema definitions that specify the structure and validation rules for your extracted data. When you link a schema to a prompt, DocRouter ensures the AI output matches your defined structure."
- Benefits with checkmarks:
  - ✓ Consistent output format across all extractions
  - ✓ Automatic validation of extracted data
  - ✓ Better integration with downstream systems
  - ✓ Clearer documentation of expected data structure

**Section 3 (White background):**
- "How to create schemas" headline
- Step-by-step guide:
  1. Navigate to Schemas page
  2. Click "Create Schema"
  3. Define your JSON Schema structure
  4. Link schema to prompts
  5. Test with sample documents
- Brief example: Show a simple schema structure (e.g., invoice schema with fields)

**Section 4 (Light colored background):**
- "Pro tip: Use Claude Code" headline
- Explanation: "Claude Code can help you create schemas and configure prompts more efficiently. Use it to generate schema definitions from examples or refine existing schemas."
- Optional in-depth link: [Learn how Claude Code creates schemas and configures prompts]({{ params.site_url }}/docs/claude-code/schemas-prompts)

**Section 5 (White background):**
- "Workflows: Automate at scale" headline
- Brief overview:
  - **N8N integration** - Connect DocRouter to email, fax, and ERP systems for automated document ingestion
  - **Temporal workflows** - Build multi-step document processing workflows that scale
- Brief explanation: "Workflows let you automate document processing end-to-end, from ingestion to data extraction to integration."
- Links:
  - [N8N Integration Guide]({{ params.site_url }}/docs/workflows/n8n)
  - [Temporal Workflows]({{ params.site_url }}/docs/workflows/temporal)
  - [REST API Documentation]({{ params.site_url }}/docs/api)

**Section 6 (Light colored background):**
- "Need a hand?" headline
- Support message with CTA: "Contact Support"

**Subject Line:**
"Learn about schemas - Structure your data extraction 🤖"

**Preview Text:**
Schemas ensure consistent, validated output from your prompts. Learn how to create and use them effectively.

---

#### Email 3: Customer Success Check (Day 7)
**Trigger:** 7 days after registration

**Purpose:** Check in on user progress, offer help, and encourage engagement with support.

**Content:**
- Check-in message
- Progress acknowledgment (if applicable)
- Common questions or tips
- Strong CTA to contact support

**Key Sections (with alternating background colors):**

**Section 1 (White background):**
- Personal greeting: "{{ contact.FIRSTNAME | default: 'there' }}, how's your DocRouter journey going?"
- Check-in message: "You've been using DocRouter for a week now. We'd love to hear how it's working for you and help with any questions or challenges you might have."
- Conditional content: If user has activity, reference it (e.g., "We noticed you've uploaded {{ contact.documents_uploaded }} documents and created {{ contact.prompts_created }} prompts!")

**Section 2 (Light colored background):**
- "Common questions" headline
- FAQ-style tips:
  - **How do I improve extraction accuracy?** → Refine your prompts, use schemas, and review results
  - **Can I automate document processing?** → Yes! Use the REST API with N8N or Temporal workflows
  - **How do I handle different document types?** → Create separate prompts and use tags for routing
  - **What if I need help?** → Our support team is here to assist you

**Section 3 (White background):**
- "We're here to help" headline
- Support message: "Whether you're just getting started or scaling your document processing, our support team can help you succeed with DocRouter."
- Primary CTA: "Contact Support"
- Secondary links: Documentation, API docs, workflow guides

**Section 4 (Light colored background):**
- "Share your feedback" headline
- Request: "Your feedback helps us improve DocRouter. What's working well? What could be better?"
- Optional CTA: "Share Feedback"

**Subject Line:**
"How's your DocRouter journey going? We're here to help 👋"

**Preview Text:**
You've been using DocRouter for a week. We're here to help with questions and hear how it's working for you.

---

## Campaign 2: Prospect Campaign (Non-Registered Users)

### Goal
Introduce DocRouter to potential users, explain value proposition, and encourage sign-up.

### Target Audience
People who have shown interest but haven't registered (e.g., visited website, downloaded resources, attended webinars, etc.)

### Email Sequence

#### Email 1: Introduction to Smart Document Router (Day 0)
**Trigger:** User added to prospect list (via form submission, event, etc.)

**Purpose:** Introduce DocRouter and its core value proposition.

**Content:**
- What is Smart Document Router?
- Problem it solves (unstructured documents from faxes, email, ERPs)
- Key differentiators (human-in-the-loop, enterprise-focused, open-source)
- High-level overview of how it works
- Use cases and industries
- Social proof (if available)

**Key Sections:**
- "Meet Smart Document Router"
- "The Problem We Solve"
- "How It Works (High-Level)"
- "Who Uses DocRouter?"
- "Why Choose DocRouter?"
- CTA: "Get Started Free" or "Learn More"

**Subject Line:**
"Transform Your Document Processing with AI"

**Preview Text:**
Meet Smart Document Router: Extract structured data from unstructured documents with AI-powered automation.

---

#### Email 2: Key Features Deep Dive (Day 3)
**Trigger:** 3 days after initial contact

**Purpose:** Highlight key features and capabilities.

**Content:**
- AI-powered extraction (multiple LLM providers)
- Human-in-the-loop verification
- Smart tagging and routing
- API and SDK integration
- Form.io integration
- Enterprise features

**Key Sections:**
- "AI-Powered Data Extraction"
- "Human Verification for Accuracy"
- "Smart Document Routing"
- "Easy Integration"
- "Enterprise-Ready"
- CTA: "See It In Action" or "Start Free Trial"

**Subject Line:**
"5 Powerful Features That Set DocRouter Apart"

**Preview Text:**
Discover AI-powered extraction, human verification, smart routing, API integration, and enterprise-ready capabilities.

---

#### Email 3: Use Cases & Success Stories (Day 7)
**Trigger:** 7 days after initial contact

**Purpose:** Show real-world applications and benefits.

**Content:**
- Common use cases (invoice processing, form extraction, etc.)
- Industry applications
- ROI and efficiency gains
- Case studies or examples (if available)
- Before/after scenarios

**Key Sections:**
- "Real-World Applications"
- "Industries We Serve"
- "The Impact: Time & Cost Savings"
- "Example Workflows"
- CTA: "Try It Yourself" or "Schedule a Demo"

**Subject Line:**
"How Companies Use DocRouter to Save Time & Money"

**Preview Text:**
See real-world applications: invoice processing, form extraction, and automated workflows that deliver ROI.

---

#### Email 4: Technical Overview & Getting Started (Day 10)
**Trigger:** 10 days after initial contact

**Purpose:** Provide technical details for technical decision-makers.

**Content:**
- Tech stack overview
- Installation options (Docker, AWS, local)
- API and SDK capabilities
- Integration examples
- Security and compliance
- Open-source benefits

**Key Sections:**
- "Built for Developers"
- "Flexible Deployment"
- "Powerful APIs & SDKs"
- "Security & Compliance"
- "Open Source Advantage"
- CTA: "View Documentation" or "Start Building"

**Subject Line:**
"Built for Developers: DocRouter Technical Overview"

**Preview Text:**
Flexible deployment options, powerful APIs, Python/TypeScript SDKs, and open-source architecture for developers.

---

#### Email 5: Final Call to Action (Day 14)
**Trigger:** 14 days after initial contact

**Purpose:** Final encouragement to sign up with special offer or urgency.

**Content:**
- Recap of key benefits
- Limited-time offer (if applicable)
- Clear next steps
- Address common objections
- Support availability

**Key Sections:**
- "Ready to Get Started?"
- "What's Next?"
- "We're Here to Help"
- CTA: "Create Free Account" (primary) + "Schedule Demo" (secondary)

**Subject Line:**
"Ready to Transform Your Document Workflow?"

**Preview Text:**
Get started with DocRouter today. Create your free account or schedule a demo to see it in action.

---

## Email Template Structure

### Design Principles (Inspired by Brevo)
1. **Alternating Background Colors** - Use white and light colored backgrounds (e.g., #f8f9fa) to create visual separation between sections
2. **Clear Visual Hierarchy** - Each section should be distinct and scannable
3. **Progressive Disclosure** - Start with foundational concepts, then build to specific tasks
4. **Practical Tips** - Include actionable tips with checkmarks (✓) for easy scanning
5. **Support Accessibility** - Always include a "Need a hand?" section with support links
6. **Professional but Friendly Tone** - Approachable language that doesn't overwhelm

### Standard Sections (All Emails)
1. **Header** - Logo/branding, gradient background (optional)
2. **Section 1 (White background)** - Personal greeting, introduction, primary CTA
3. **Section 2 (Light background)** - "How it works" with step-by-step guide or visual reference
4. **Section 3 (White background)** - Tips, best practices, or additional information with checkmarks
5. **Section 4 (Light background)** - "Need a hand?" support section
6. **Footer** - Copyright, unsubscribe (`{{ unsubscribe }}`), social links, "View in browser" (`{{ mirror }}`)

### Visual Elements
- **Checkmarks (✓)** for tips and best practices
- **Numbered steps** for process guides
- **Clear CTAs** - Primary action button, secondary text links
- **Illustration references** - Mention visuals/animations that would be in the actual HTML
- **Color scheme** - Primary brand color (#0070f3 blue) for CTAs, alternating white/light backgrounds

### Brevo Template Variables

#### Contact Attributes (Campaigns & Automations)
Use these for personalization in all emails:

**Built-in Contact Attributes:**
- `{{ contact.FIRSTNAME }}` - User's first name
- `{{ contact.LASTNAME }}` - User's last name
- `{{ contact.EMAIL }}` - User's email address
- `{{ contact.COMPANY }}` - Company/organization name
- `{{ contact.CITY }}` - City
- `{{ contact.COUNTRY }}` - Country
- `{{ contact.STATE }}` - State/Province

**With Fallback (Recommended):**
- `{{ contact.FIRSTNAME | default: 'there' }}` - Safe greeting if name missing
- `{{ contact.COMPANY | default: 'your organization' }}` - Safe company reference

**Custom Contact Attributes (to be created in Brevo):**
- `{{ contact.organization_name }}` - DocRouter organization name (for registered users)
- `{{ contact.user_role }}` - User role (admin, user, etc.)
- `{{ contact.signup_date }}` - Account creation date
- `{{ contact.documents_uploaded }}` - Count of uploaded documents
- `{{ contact.prompts_created }}` - Count of created prompts
- `{{ contact.last_activity_date }}` - Last activity timestamp

#### Transactional Email Attributes (API/SMTP)
Use `{{ params.* }}` for dynamic data passed via API:

**For Welcome/Verification Emails:**
- `{{ params.verification_url }}` - Email verification link
- `{{ params.site_url }}` - Base URL of the site
- `{{ params.organization_name }}` - Organization name

**For Onboarding Emails:**
- `{{ params.site_url }}` - Base URL for CTAs
- `{{ params.document_count }}` - Number of documents uploaded (if applicable)
- `{{ params.prompt_count }}` - Number of prompts created (if applicable)
- `{{ params.dashboard_url }}` - Direct link to user dashboard

**For Prospect Emails:**
- `{{ params.site_url }}` - Base URL for CTAs
- `{{ params.signup_url }}` - Direct signup link
- `{{ params.demo_url }}` - Link to schedule demo

#### System Attributes (Mandatory)
- `{{ unsubscribe }}` - Unsubscribe link (required in footer)
- `{{ update_profile }}` - Manage preferences link
- `{{ mirror }}` - View in browser link

#### Sender Attributes
- `{{ sender.name }}` - Sender name
- `{{ sender.email }}` - Sender email
- `{{ sender.company }}` - Sender company
- `{{ sender.address }}` - Sender address

#### Conditional Logic (Advanced)
```html
{% if contact.FIRSTNAME %}
  Hi {{ contact.FIRSTNAME }},
{% else %}
  Hi there,
{% endif %}
```

```html
{% if contact.documents_uploaded > 0 %}
  We noticed you've uploaded {{ contact.documents_uploaded }} documents!
{% endif %}
```

### Recommended Attribute Usage by Email Type

**Onboarding Emails (Registered Users):**
- Greeting: `{{ contact.FIRSTNAME | default: 'there' }}`
- Organization: `{{ contact.organization_name | default: contact.COMPANY | default: 'your organization' }}`
- Dynamic data: Use `{{ params.* }}` for site URLs, counts, etc.

**Prospect Emails (Non-Registered):**
- Greeting: `{{ contact.FIRSTNAME | default: 'there' }}`
- Company: `{{ contact.COMPANY | default: 'your company' }}`
- Dynamic data: Use `{{ params.* }}` for signup URLs, demo links, etc.

---

## Implementation Notes

### Brevo Setup Requirements

**1. Create Custom Contact Attributes**
Before implementing the email campaigns, create these custom attributes in Brevo:
- Go to **Contacts → Attributes → Add Attribute**
- Create the following attributes:
  - `organization_name` (Text) - DocRouter organization name
  - `user_role` (Text) - User role (admin, user, etc.)
  - `signup_date` (Date) - Account creation date
  - `documents_uploaded` (Number) - Count of uploaded documents
  - `prompts_created` (Number) - Count of created prompts
  - `last_activity_date` (Date) - Last activity timestamp

**2. Sync Contact Data**
- When users register, sync their data to Brevo contacts
- Update custom attributes when users perform actions (upload docs, create prompts)
- Use Brevo API or webhooks to keep contact data in sync

**3. Transactional Email Setup**
- For transactional emails (welcome, verification), use Brevo SMTP/API
- Pass dynamic data via `params` object in API calls
- Example API payload structure:
  ```json
  {
    "to": [{ "email": "user@example.com" }],
    "params": {
      "verification_url": "https://docrouter.ai/auth/verify?token=...",
      "site_url": "https://docrouter.ai",
      "organization_name": "Acme Corp"
    }
  }
  ```

**4. Campaign vs Transactional**
- **Campaign emails** (onboarding sequence, prospect sequence): Use Brevo Campaigns/Automations with contact attributes
- **Transactional emails** (verification, password reset): Use Brevo SMTP/API with `params`

### Design Approach (Lessons from Brevo)
- **Start with foundation, not tasks:** Email 1 focuses on understanding the workflow before jumping into tasks
- **Alternating backgrounds:** Use white and light colored backgrounds (#f8f9fa or similar) to create visual separation
- **Scannable sections:** Each section should be distinct and easy to scan
- **Progressive disclosure:** Build knowledge progressively - foundation → basic tasks → advanced features
- **Practical tips with checkmarks:** Use ✓ symbols for actionable tips that are easy to scan
- **Support always accessible:** Include "Need a hand?" section in every email
- **Professional but friendly tone:** Approachable language that doesn't overwhelm

### Timing Considerations
- **Onboarding emails:** Send based on user actions (uploaded docs, created prompts) when possible, with time-based fallbacks
- **Prospect emails:** Time-based sequence, but pause if user registers
- **Respect user preferences:** Always include `{{ unsubscribe }}` link and honor opt-outs

### Personalization
- **Use Brevo contact attributes** for personalization:
  - Greeting: `{{ contact.FIRSTNAME | default: 'there' }}`
  - Organization: `{{ contact.organization_name | default: contact.COMPANY }}`
- **Use conditional logic** to personalize content based on user activity:
  - `{% if contact.documents_uploaded > 0 %}` - Reference actual uploads
  - `{% if contact.prompts_created > 0 %}` - Reference prompt creation
- **Use transactional params** for dynamic links and counts:
  - `{{ params.document_count }}` - Show actual document count
  - `{{ params.dashboard_url }}` - Direct links to specific pages
- **Track engagement** in Brevo and adjust sequence accordingly
- **For registered users:** Reference their actual activity using custom attributes

### A/B Testing Opportunities
- Subject lines
- CTA button text and placement
- Email length (short vs. detailed)
- Visual design elements

### Metrics to Track
- Open rates
- Click-through rates (CTAs)
- Conversion rates (sign-ups, document uploads, prompt creation)
- Unsubscribe rates
- Time to first action (upload, prompt creation)

---

## Next Steps

1. **Set up Brevo custom attributes** (see Implementation Notes above)
2. **Create email templates** for each email in the sequence using Brevo attribute syntax
3. **Set up Brevo automation workflows** for campaign emails (onboarding & prospect sequences)
4. **Integrate Brevo API/SMTP** for transactional emails (verification, password reset)
5. **Sync contact data** from DocRouter to Brevo (on registration, activity updates)
6. **Set up email triggers** in the application to update Brevo contact attributes
7. **Test email delivery** across different email clients
8. **Monitor and optimize** using Brevo analytics (open rates, click rates, conversions)

---

## File Naming Convention

For email templates:

**Onboarding Campaign (Registered Users):**
- `onboarding-email-1-upload-tailor-results.html` - Email 1 (Day 0): Upload, tailor prompt, see results
- `onboarding-email-2-schemas.html` - Email 2 (Day 3): Learn about schemas
- `onboarding-email-3-checkin.html` - Email 3 (Day 7): Customer success check

**Prospect Campaign (Non-Registered Users):**
- `prospect-introduction.html` - Email 1 (Day 0): Prospect intro
- `prospect-features.html` - Email 2 (Day 3): Features
- `prospect-use-cases.html` - Email 3 (Day 7): Use cases
- `prospect-technical.html` - Email 4 (Day 10): Technical overview
- `prospect-final-cta.html` - Email 5 (Day 14): Final CTA

**Note:** The existing `welcome-email-template.html` and `onboarding-email-*.html` files may need to be updated or replaced to match the new structure.
