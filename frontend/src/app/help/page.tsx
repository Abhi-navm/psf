'use client';

import { HelpCircle, Book, MessageCircle, Video, Mail } from 'lucide-react';

export default function HelpPage() {
  const faqs = [
    {
      question: "How does the AI analyze my pitch?",
      answer: "Our AI uses multiple models to analyze different aspects: speech transcription (Whisper), voice tone analysis (Librosa), facial expression detection (DeepFace), body language analysis (MediaPipe), and content quality assessment (Llama 3)."
    },
    {
      question: "What video formats are supported?",
      answer: "We support MP4, MOV, AVI, MKV, and WebM formats. Maximum file size is 500MB and maximum duration is 30 minutes."
    },
    {
      question: "How long does analysis take?",
      answer: "Analysis typically takes 30-60 seconds for a 5-minute video, depending on server load and video complexity."
    },
    {
      question: "What does each score mean?",
      answer: "Scores range from 0-100. Above 85 is Excellent, 70-85 is Good, 50-70 is Average, and below 50 Needs Work. Each category (voice, facial, pose, content) contributes to the overall score."
    },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Help & Support</h1>
        <p className="text-slate-500 mt-1">Get help with using AI Pitch Analyzer</p>
      </div>

      <div className="max-w-3xl">
        {/* Quick links */}
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          <div className="card p-5 text-center hover:shadow-md transition-shadow cursor-pointer">
            <Book className="w-8 h-8 text-indigo-500 mx-auto mb-3" />
            <h3 className="font-medium text-slate-700">Documentation</h3>
            <p className="text-sm text-slate-400 mt-1">Read the full guide</p>
          </div>
          <div className="card p-5 text-center hover:shadow-md transition-shadow cursor-pointer">
            <Video className="w-8 h-8 text-emerald-500 mx-auto mb-3" />
            <h3 className="font-medium text-slate-700">Video Tutorials</h3>
            <p className="text-sm text-slate-400 mt-1">Watch how-to videos</p>
          </div>
          <div className="card p-5 text-center hover:shadow-md transition-shadow cursor-pointer">
            <Mail className="w-8 h-8 text-purple-500 mx-auto mb-3" />
            <h3 className="font-medium text-slate-700">Contact Support</h3>
            <p className="text-sm text-slate-400 mt-1">Get personalized help</p>
          </div>
        </div>

        {/* FAQs */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-slate-400" />
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {faqs.map((faq, idx) => (
              <div key={idx} className="p-4 bg-slate-50 rounded-lg">
                <h3 className="font-medium text-slate-700 mb-2">{faq.question}</h3>
                <p className="text-sm text-slate-500">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Contact */}
        <div className="card p-6 mt-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-slate-400" />
            Still need help?
          </h2>
          <textarea
            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
            rows={4}
            placeholder="Describe your issue..."
          />
          <button className="px-6 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white font-medium rounded-lg transition-colors">
            Send Message
          </button>
        </div>
      </div>
    </div>
  );
}
