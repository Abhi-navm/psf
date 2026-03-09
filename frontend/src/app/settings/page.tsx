'use client';

import { useState, useEffect } from 'react';
import { User, Bell, Palette, Video, Check, Loader2, Trash2, Star, RefreshCw, Upload } from 'lucide-react';
import { 
  getGoldenPitchDecks, 
  getVideos, 
  createGoldenPitchDeck, 
  deleteGoldenPitchDeck, 
  setActiveGoldenPitchDeck,
  reprocessGoldenPitchDeck,
  uploadVideo,
  GoldenPitchDeck 
} from '@/lib/api';

export default function SettingsPage() {
  const [goldenDecks, setGoldenDecks] = useState<GoldenPitchDeck[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [newDeckName, setNewDeckName] = useState('');
  const [newDeckDescription, setNewDeckDescription] = useState('');
  const [uploadMode, setUploadMode] = useState<'upload' | 'existing'>('upload');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [decksRes, videosRes] = await Promise.all([
        getGoldenPitchDecks(),
        getVideos()
      ]);
      setGoldenDecks(decksRes.items);
      setVideos(videosRes.videos || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGoldenDeck = async () => {
    if (uploadMode === 'upload' && !selectedFile) return;
    if (uploadMode === 'existing' && !selectedVideoId) return;
    if (!newDeckName) return;
    
    setCreating(true);
    try {
      let videoId = selectedVideoId;
      
      // If upload mode, upload the file first
      if (uploadMode === 'upload' && selectedFile) {
        setUploading(true);
        const uploadResult = await uploadVideo(selectedFile);
        videoId = uploadResult.id;
        setUploading(false);
      }
      
      await createGoldenPitchDeck({
        video_id: videoId,
        name: newDeckName,
        description: newDeckDescription || undefined,
        set_as_active: true,
      });
      setNewDeckName('');
      setNewDeckDescription('');
      setSelectedVideoId('');
      setSelectedFile(null);
      await loadData();
    } catch (error) {
      console.error('Failed to create golden pitch deck:', error);
      setUploading(false);
    } finally {
      setCreating(false);
    }
  };

  const handleSetActive = async (id: string) => {
    try {
      await setActiveGoldenPitchDeck(id);
      await loadData();
    } catch (error) {
      console.error('Failed to set active:', error);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this golden pitch deck?')) return;
    try {
      await deleteGoldenPitchDeck(id);
      await loadData();
    } catch (error) {
      console.error('Failed to delete:', error);
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      await reprocessGoldenPitchDeck(id);
      await loadData();
    } catch (error) {
      console.error('Failed to reprocess:', error);
    }
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and preferences</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Golden Pitch Deck */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Star className="w-5 h-5 text-yellow-500" />
            Golden Pitch Deck (Reference Video)
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            Set a master reference video. All new video analyses will be compared against this golden pitch deck.
          </p>

          {/* Existing Golden Decks */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            </div>
          ) : goldenDecks.length > 0 ? (
            <div className="space-y-3 mb-6">
              {goldenDecks.map((deck) => (
                <div 
                  key={deck.id} 
                  className={`p-4 rounded-lg border-2 transition-colors ${
                    deck.is_active 
                      ? 'border-yellow-400 bg-yellow-50' 
                      : 'border-slate-200 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800">{deck.name}</span>
                        {deck.is_active && (
                          <span className="px-2 py-0.5 bg-yellow-400 text-yellow-800 text-xs font-medium rounded-full">
                            Active
                          </span>
                        )}
                        {!deck.is_processed && (
                          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Processing
                          </span>
                        )}
                        {deck.processing_error && (
                          <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded-full">
                            Error
                          </span>
                        )}
                      </div>
                      {deck.description && (
                        <p className="text-sm text-slate-500 mt-1">{deck.description}</p>
                      )}
                      {deck.is_processed && deck.keywords && (
                        <p className="text-xs text-slate-400 mt-1">
                          {(deck.keywords as any)?.keywords?.length || 0} keywords extracted
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {!deck.is_active && (
                        <button
                          onClick={() => handleSetActive(deck.id)}
                          className="p-2 text-slate-400 hover:text-yellow-500 transition-colors"
                          title="Set as active"
                        >
                          <Star className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleReprocess(deck.id)}
                        className="p-2 text-slate-400 hover:text-blue-500 transition-colors"
                        title="Reprocess"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(deck.id)}
                        className="p-2 text-slate-400 hover:text-red-500 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 bg-slate-50 rounded-lg mb-6">
              <Video className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-slate-500 text-sm">No golden pitch deck set</p>
              <p className="text-slate-400 text-xs">Create one below to enable comparison</p>
            </div>
          )}

          {/* Create New */}
          <div className="border-t pt-4">
            <h3 className="text-sm font-medium text-slate-700 mb-3">Create New Golden Pitch Deck</h3>
            
            {/* Toggle between upload and existing */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setUploadMode('upload')}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  uploadMode === 'upload'
                    ? 'bg-indigo-500 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Upload New Video
              </button>
              <button
                onClick={() => setUploadMode('existing')}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  uploadMode === 'existing'
                    ? 'bg-indigo-500 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Use Existing Video
              </button>
            </div>
            
            <div className="space-y-3">
              {uploadMode === 'upload' ? (
                <div>
                  <label className="block text-sm text-slate-600 mb-1">Upload Video File</label>
                  <input 
                    type="file" 
                    accept="video/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setSelectedFile(file);
                        // Auto-fill name from filename if empty
                        if (!newDeckName) {
                          const baseName = file.name.replace(/\.[^/.]+$/, '');
                          setNewDeckName(baseName);
                        }
                      }
                    }}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-600 hover:file:bg-indigo-100"
                  />
                  {selectedFile && (
                    <p className="text-xs text-slate-500 mt-1">
                      Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <label className="block text-sm text-slate-600 mb-1">Select Video</label>
                  <select 
                    value={selectedVideoId}
                    onChange={(e) => setSelectedVideoId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">Choose a video...</option>
                    {videos.map((video) => (
                      <option key={video.id} value={video.id}>
                        {video.original_filename} 
                      </option>
                    ))}
                  </select>
                  {videos.length === 0 && (
                    <p className="text-xs text-slate-400 mt-1">
                      No videos uploaded yet. Use "Upload New Video" instead.
                    </p>
                  )}
                </div>
              )}
              <div>
                <label className="block text-sm text-slate-600 mb-1">Name</label>
                <input 
                  type="text" 
                  value={newDeckName}
                  onChange={(e) => setNewDeckName(e.target.value)}
                  placeholder="e.g., Q1 Sales Pitch Template"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" 
                />
              </div>
              <div>
                <label className="block text-sm text-slate-600 mb-1">Description (optional)</label>
                <input 
                  type="text" 
                  value={newDeckDescription}
                  onChange={(e) => setNewDeckDescription(e.target.value)}
                  placeholder="Brief description..."
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" 
                />
              </div>
              <button 
                onClick={handleCreateGoldenDeck}
                disabled={
                  (uploadMode === 'upload' && !selectedFile) ||
                  (uploadMode === 'existing' && !selectedVideoId) ||
                  !newDeckName || 
                  creating
                }
                className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 disabled:bg-slate-300 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {uploading ? 'Uploading...' : 'Creating...'}
                  </>
                ) : (
                  <>
                    <Star className="w-4 h-4" />
                    Create Golden Pitch Deck
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Account */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <User className="w-5 h-5 text-slate-400" />
            Account
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Name</label>
              <input type="text" defaultValue="User" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Email</label>
              <input type="email" defaultValue="user@example.com" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-slate-400" />
            Notifications
          </h2>
          <div className="space-y-3">
            <label className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Email notifications when analysis completes</span>
              <input type="checkbox" defaultChecked className="rounded border-slate-300 text-indigo-500 focus:ring-indigo-500" />
            </label>
            <label className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Weekly analysis summary</span>
              <input type="checkbox" className="rounded border-slate-300 text-indigo-500 focus:ring-indigo-500" />
            </label>
          </div>
        </div>

        {/* Appearance */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Palette className="w-5 h-5 text-slate-400" />
            Appearance
          </h2>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-2">Theme</label>
            <select className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option>Light</option>
              <option>Dark</option>
              <option>System</option>
            </select>
          </div>
        </div>

        <button className="px-6 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white font-medium rounded-lg transition-colors">
          Save Changes
        </button>
      </div>
    </div>
  );
}
