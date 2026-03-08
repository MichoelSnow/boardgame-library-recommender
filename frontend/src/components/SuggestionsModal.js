import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import { createSuggestion } from '../api/suggestions';

const SuggestionsModal = ({ open, onClose }) => {
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!comment.trim()) {
      setError('Please enter a suggestion before submitting.');
      return;
    }

    if (comment.length > 1000) {
      setError('Suggestion must be 1000 characters or less.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await createSuggestion(comment.trim());
      setSuccess(true);
      setComment('');
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 2000);
    } catch (err) {
      console.error('Suggestion submission failed:', err);
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Failed to submit suggestion. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setComment('');
      setError('');
      setSuccess(false);
      onClose();
    }
  };

  const characterCount = comment.length;
  const maxLength = 1000;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        Submit a Suggestion
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Help us improve this site! Share your suggestions for new features, improvements, or bug reports.
          </Typography>
          
          {success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Thank you for your suggestion! It has been submitted successfully.
            </Alert>
          )}
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <TextField
            fullWidth
            multiline
            rows={6}
            label="Your suggestion"
            placeholder="Tell us about features you'd like to see, issues you've encountered, or ways we can improve the site..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={loading || success}
            error={characterCount > maxLength}
            helperText={`${characterCount}/${maxLength} characters`}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          disabled={loading || success || !comment.trim() || characterCount > maxLength}
          startIcon={loading && <CircularProgress size={20} />}
        >
          {loading ? 'Submitting...' : 'Submit Suggestion'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SuggestionsModal;
