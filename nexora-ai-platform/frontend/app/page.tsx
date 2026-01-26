'use client'

import { useState, useEffect } from 'react'
import { PlusCircle, FileText, Users, BarChart3, Settings, Bot, Sparkles } from 'lucide-react'

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)

  // Mock authentication check
  useEffect(() => {
    // In a real app, this would check for valid JWT token
    const mockUser = {
      name: 'Demo User',
      email: 'demo@nexora.ai',
      role: 'CREATOR'
    }
    setUser(mockUser)
    setIsAuthenticated(true)
  }, [])

  if (!isAuthenticated) {
    return <LoginPage onLogin={() => setIsAuthenticated(true)} />
  }

  return <Dashboard user={user} />
}

function LoginPage({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow-lg">
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <Bot className="h-12 w-12 text-blue-600" />
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Nexora AI</h2>
          <p className="mt-2 text-gray-600">AI-powered content automation platform</p>
        </div>
        
        <div className="space-y-4">
          <button
            onClick={onLogin}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Sign in with Demo Account
          </button>
          
          <div className="text-center text-sm text-gray-500">
            Demo Mode - No authentication required
          </div>
        </div>
      </div>
    </div>
  )
}

function Dashboard({ user }: { user: any }) {
  const [activeTab, setActiveTab] = useState('content')

  const stats = [
    { name: 'Content Generated', value: '24', icon: FileText },
    { name: 'Active Workflows', value: '3', icon: Bot },
    { name: 'Team Members', value: '8', icon: Users },
    { name: 'Success Rate', value: '94%', icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <Bot className="h-8 w-8 text-blue-600 mr-3" />
              <h1 className="text-2xl font-bold text-gray-900">Nexora AI</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">Welcome, {user.name}</span>
              <div className="h-8 w-8 bg-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-medium">
                  {user.name.charAt(0)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat) => (
            <div key={stat.name} className="bg-white p-6 rounded-lg shadow-sm">
              <div className="flex items-center">
                <stat.icon className="h-8 w-8 text-blue-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Navigation Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'content', name: 'Content Generation', icon: Sparkles },
              { id: 'workflows', name: 'Workflows', icon: Bot },
              { id: 'analytics', name: 'Analytics', icon: BarChart3 },
              { id: 'settings', name: 'Settings', icon: Settings },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="h-5 w-5 mr-2" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Content Area */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          {activeTab === 'content' && <ContentGeneration />}
          {activeTab === 'workflows' && <WorkflowsTab />}
          {activeTab === 'analytics' && <AnalyticsTab />}
          {activeTab === 'settings' && <SettingsTab />}
        </div>
      </div>
    </div>
  )
}

function ContentGeneration() {
  const [prompt, setPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedContent, setGeneratedContent] = useState('')

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    
    setIsGenerating(true)
    // Simulate API call
    setTimeout(() => {
      setGeneratedContent(`Generated content based on: "${prompt}"\n\nThis is a demo of the Nexora AI platform. In the full implementation, this would connect to Amazon Bedrock and LangChain to generate high-quality content using RAG (Retrieval-Augmented Generation) technology.\n\nKey features:\n- AI-powered content generation\n- Human-in-the-loop review\n- Multi-platform publishing\n- Analytics and insights`)
      setIsGenerating(false)
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Content Generation</h2>
        <button className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          <PlusCircle className="h-4 w-4 mr-2" />
          New Project
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Content Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the content you want to generate..."
              className="w-full h-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <button
            onClick={handleGenerate}
            disabled={isGenerating || !prompt.trim()}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? 'Generating...' : 'Generate Content'}
          </button>
        </div>

        <div className="space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            Generated Content
          </label>
          <div className="h-64 p-4 border border-gray-300 rounded-md bg-gray-50 overflow-y-auto">
            {generatedContent ? (
              <pre className="whitespace-pre-wrap text-sm text-gray-800">
                {generatedContent}
              </pre>
            ) : (
              <p className="text-gray-500 italic">Generated content will appear here...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function WorkflowsTab() {
  return (
    <div className="text-center py-12">
      <Bot className="h-16 w-16 text-gray-400 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-2">Workflow Management</h3>
      <p className="text-gray-600">Configure automation levels and human review processes</p>
      <div className="mt-6 text-sm text-gray-500">
        Feature coming soon - Part of the full implementation
      </div>
    </div>
  )
}

function AnalyticsTab() {
  return (
    <div className="text-center py-12">
      <BarChart3 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-2">Analytics Dashboard</h3>
      <p className="text-gray-600">Track content performance and engagement metrics</p>
      <div className="mt-6 text-sm text-gray-500">
        Feature coming soon - Part of the full implementation
      </div>
    </div>
  )
}

function SettingsTab() {
  return (
    <div className="text-center py-12">
      <Settings className="h-16 w-16 text-gray-400 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-2">Platform Settings</h3>
      <p className="text-gray-600">Configure AI models, integrations, and team settings</p>
      <div className="mt-6 text-sm text-gray-500">
        Feature coming soon - Part of the full implementation
      </div>
    </div>
  )
}