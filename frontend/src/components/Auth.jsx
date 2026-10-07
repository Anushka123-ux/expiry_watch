import React, { useState } from 'react';
import api from '../api';
import { Lock, Mail, ArrowRight } from 'lucide-react';

export default function Auth({ onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const endpoint = isLogin ? '/login' : '/register';

    try {
      const res = await api.post(endpoint, { email, password });
      if (isLogin) {
        localStorage.setItem('token', res.data.access_token);
        onLoginSuccess();
      } else {
        // Automatically switch to login on successful signup
        setIsLogin(true);
        setError('Account created! Please log in.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <div className="w-full max-w-md p-8 bg-white border border-slate-200 rounded-xl shadow-sm">
        <h1 className="text-2xl font-bold text-center text-slate-800 mb-2">ExpiryWatch</h1>
        <p className="text-sm text-center text-slate-500 mb-6">
          {isLogin ? 'Sign in to access your tracked documents' : 'Create an account to start tracking'}
        </p>

        {error && (
          <div className="p-3 mb-4 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-1 text-xs font-semibold text-slate-600 uppercase">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="name@example.com"
              />
            </div>
          </div>

          <div>
            <label className="block mb-1 text-xs font-semibold text-slate-600 uppercase">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-sm transition"
          >
            {loading ? 'Processing...' : isLogin ? 'Sign In' : 'Sign Up'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-600">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button
            onClick={() => { setIsLogin(!isLogin); setError(''); }}
            className="text-blue-600 font-semibold hover:underline"
          >
            {isLogin ? 'Sign Up' : 'Log In'}
          </button>
        </div>
      </div>
    </div>
  );
}