import React, { useState, useEffect } from 'react';
import api from './api';
import Auth from './components/Auth';
import VerifyModal from './components/VerifyModal';
import { UploadCloud, FileText, Calendar, LogOut, CheckCircle, AlertTriangle } from 'lucide-react';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [verifyData, setVerifyData] = useState(null);

  useEffect(() => {
    if (token) {
      fetchDocuments();
    }
  }, [token]);

  const fetchDocuments = async () => {
    try {
      const res = await api.get('/documents');
      setDocuments(res.data.documents || []);
    } catch (err) {
      if (err.response?.status === 401) {
        handleLogout();
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/extract', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setVerifyData(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const getStatusBadge = (expiryDate) => {
    const today = new Date();
    const exp = new Date(expiryDate);
    const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">Expired</span>;
    }
    if (diffDays <= 30) {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">Expires in {diffDays}d</span>;
    }
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">Active</span>;
  };

  if (!token) {
    return <Auth onLoginSuccess={() => setToken(localStorage.getItem('token'))} />;
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Navbar */}
      <header className="flex justify-between items-center pb-6 border-b border-slate-200 mb-8">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">ExpiryWatch</h1>
          <p className="text-xs text-slate-500">Document Expiration & Alert Engine</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center text-xs font-medium text-slate-600 hover:text-red-600 transition"
        >
          <LogOut className="w-4 h-4 mr-1.5" /> Sign Out
        </button>
      </header>

      {/* Upload Box */}
      <div className="mb-8 p-6 bg-white border border-dashed border-slate-300 rounded-xl flex flex-col items-center justify-center text-center">
        <UploadCloud className="w-10 h-10 text-blue-500 mb-2" />
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Upload Document to Track</h3>
        <p className="text-xs text-slate-400 mb-4">Supports PDF, PNG, JPG (Scanned documents or digital invoices)</p>
        <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition">
          {uploading ? 'Extracting text via OCR...' : 'Select Document'}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg"
            disabled={uploading}
            onChange={handleFileUpload}
          />
        </label>
      </div>

      {/* Tracked Documents Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
          <h2 className="text-sm font-bold text-slate-800">Tracked Documents ({documents.length})</h2>
        </div>
        {documents.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">No documents tracked yet. Upload one above.</div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <th className="px-6 py-3">Document</th>
                <th className="px-6 py-3">Expiry Date</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-slate-50/50">
                  <td className="px-6 py-4 flex items-center font-medium text-slate-800">
                    <FileText className="w-4 h-4 mr-2 text-slate-400" />
                    {doc.document_type}
                  </td>
                  <td className="px-6 py-4 text-slate-600">
                    <div className="flex items-center">
                      <Calendar className="w-4 h-4 mr-1.5 text-slate-400" />
                      {doc.expiry_date}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(doc.expiry_date)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Human-in-the-loop Verification Modal */}
      {verifyData && (
        <VerifyModal
          data={verifyData}
          onClose={() => setVerifyData(null)}
          onConfirmed={fetchDocuments}
        />
      )}
    </div>
  );
}