import React, { useState } from 'react';
import api from '../api';
import { CheckCircle2, X } from 'lucide-react';

export default function VerifyModal({ data, onClose, onConfirmed }) {
  const [docType, setDocType] = useState(data.document_type || 'General Document');
  const [expiryDate, setExpiryDate] = useState(data.expiry_date || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConfirm = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await api.post('/confirm', {
        document_type: docType,
        expiry_date: expiryDate
      });
      onConfirmed();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail?.[0]?.msg || 'Validation failed. Check date format.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-lg border border-slate-200 w-full max-w-md overflow-hidden">
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-800">Verify Extracted Details</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleConfirm} className="p-6 space-y-4">
          <div className="bg-slate-50 p-3 rounded-lg text-xs text-slate-500 mb-2">
            Extraction engine: <span className="font-semibold text-slate-700 uppercase">{data.extraction_method || 'Hybrid OCR'}</span>
          </div>

          {error && <div className="text-xs text-red-600 bg-red-50 p-2 rounded border border-red-200">{error}</div>}

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">DOCUMENT TYPE</label>
            <input
              type="text"
              required
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full text-sm px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">EXPIRY DATE (YYYY-MM-DD)</label>
            <input
              type="date"
              required
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
              className="w-full text-sm px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div className="pt-2 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 text-slate-700 text-sm rounded-lg hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg flex items-center"
            >
              <CheckCircle2 className="w-4 h-4 mr-1.5" />
              {loading ? 'Saving...' : 'Confirm & Track'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}