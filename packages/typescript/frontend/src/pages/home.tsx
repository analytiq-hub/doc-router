import React from 'react';
import { appName } from '@/config/branding';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

const Home = () => {
  return (
    <div className="min-h-full bg-muted/40">
      <div className="mx-auto max-w-4xl space-y-8 px-4 py-12 sm:px-6">
        <header className="hidden space-y-2 text-center md:block">
          <h1 className="text-4xl font-semibold tracking-tight text-foreground">{appName}</h1>
          <p className="text-lg text-muted-foreground">
            AI-powered document processing that connects directly to your ERP
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>About</CardTitle>
            <CardDescription>
              How {appName} fits into your document and ERP workflows
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-muted-foreground">
              {appName} transforms unstructured documents into structured ERP data automatically.
              It processes incoming documents from multiple sources and enriches them with AI for
              seamless integration.
            </p>
            <div className="rounded-lg border bg-muted/50 p-4">
              <h3 className="mb-3 text-sm font-medium text-foreground">Key features</h3>
              <ul className="list-inside list-disc space-y-2 text-sm text-muted-foreground">
                <li>Ingests unstructured docs from faxes, email, and ERPs</li>
                <li>Autonomous processing with LLMs and NLP</li>
                <li>Human-in-the-loop design for financial accuracy</li>
                <li>Direct ERP integration capabilities</li>
                <li>REST APIs for all functions</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contact us</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>Get in touch for inquiries, partnerships, or more information about our products.</p>
            <p>
              Email:{' '}
              <a href="mailto:andrei@analytiqhub.com" className="text-primary hover:underline">
                andrei@analytiqhub.com
              </a>
            </p>
            <p>
              Website:{' '}
              <a href="https://analytiqhub.com" className="text-primary hover:underline">
                analytiqhub.com
              </a>
            </p>
          </CardContent>
        </Card>

        <footer className="space-y-2 text-center text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} DocRouter.AI. All rights reserved.</p>
          <a
            href="https://github.com/analytiq-hub/doc-router"
            className="text-primary hover:underline"
          >
            View on GitHub
          </a>
        </footer>
      </div>
    </div>
  );
};

export default Home;
