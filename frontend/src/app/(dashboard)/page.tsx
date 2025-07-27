import React from 'react';

const Home = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Hero Section */}
        <header className="text-center mb-12 hidden md:block">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            <span>Smart Document Router</span>
          </h1>
          <div className="text-xl text-gray-600 space-y-1">
            <p>AI-powered document processing</p>
            <p>that connects directly to your ERP</p>
          </div>
        </header>
        
        <main>
          {/* About Section */}
          <section className="bg-white rounded-lg shadow-lg p-8 mb-12">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">About</h2>
            <p className="text-gray-600 mb-6">
              The Smart Document Router transforms unstructured documents into structured ERP data automatically. 
              It processes incoming documents from multiple sources and enriches them with AI for seamless integration.
            </p>
            
            <div className="bg-gray-50 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Key Features</h3>
              <ul className="list-disc list-inside text-gray-600 space-y-2">
                <li>Ingests unstructured docs from faxes, email, and ERPs</li>
                <li>Autonomous processing with LLMs and NLP</li>
                <li>Human-in-the-loop design for financial accuracy</li>
                <li>Direct ERP integration capabilities</li>
                <li>REST APIs for all functions</li>
              </ul>
            </div>
          </section>

          {/* Contact Section */}
          <section className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">Contact Us</h2>
            <p className="text-gray-600 mb-4">
              Get in touch for inquiries, partnerships, or more information about our products.
            </p>
            <ul className="text-gray-600 space-y-2">
              <li>Email: <a href="mailto:andrei@analytiqhub.com" className="text-blue-600 hover:text-blue-800">andrei@analytiqhub.com</a></li>
              <li>Website: <a href="https://analytiqhub.com" className="text-blue-600 hover:text-blue-800">analytiqhub.com</a></li>
            </ul>
          </section>
        </main>
        
        <footer className="mt-12 text-center text-gray-600">
          <p>&copy; 2024 DocRouter.AI. All rights reserved.</p>
          <div className="mt-4">
            <a 
              href="https://github.com/analytiq-hub/doc-router" 
              className="text-blue-600 hover:text-blue-800"
            >
              View on GitHub
            </a>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Home;
