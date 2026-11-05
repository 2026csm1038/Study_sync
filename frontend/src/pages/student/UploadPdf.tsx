import React, { useState, useRef } from "react";
import "../../upload.css"; // Ensure you import your corresponding CSS file

export default function UploadPdf() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [courseCode, setCourseCode] = useState("");
  const [department, setDepartment] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      validateAndSetFile(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      validateAndSetFile(file);
    }
  };

  const validateAndSetFile = (file: File) => {
    if (file.type !== "application/pdf") {
      setErrorMessage("Only PDF files are allowed.");
      setSelectedFile(null);
      return;
    }
    setErrorMessage(null);
    setSelectedFile(file);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage("Please select a PDF file to upload.");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    // Simulate upload process
    setTimeout(() => {
      setIsUploading(false);
      setSuccessMessage("PDF uploaded successfully and published instantly!");
      setSelectedFile(null);
      setCourseCode("");
      setDepartment("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }, 1500);
  };

  return (
    <>
      <div className="up-card">
        <h2>Upload PDF Document</h2>

        <form onSubmit={handleSubmit} className="up-fieldset">
          {/* Drop Zone */}
          <div
            className={`up-drop ${dragActive ? "up-drop-active" : ""} ${
              errorMessage ? "up-drop-error" : ""
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="up-file-input"
              onChange={handleFileChange}
            />
            <strong>Choose a PDF file or drag it here</strong>
            <span>PDF files only (max size limits apply)</span>
          </div>

          {/* Selected File Display */}
          {selectedFile && (
            <div className="up-selected">
              <strong>{selectedFile.name}</strong>
              <span>{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
              <button type="button" onClick={handleRemoveFile} title="Remove file">
                ✕
              </button>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && <p className="up-error">{errorMessage}</p>}

          {/* Form Fields Grid */}
          <div className="up-grid">
            <label className="up-field">
              Course Code
              <input
                type="text"
                placeholder="e.g. CS101"
                value={courseCode}
                onChange={(e) => setCourseCode(e.target.value)}
                required
              />
            </label>

            <label className="up-field">
              Department
              <input
                type="text"
                placeholder="e.g. Computer Science"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                required
              />
            </label>
          </div>

          <div className="up-notice">
            Note: If the course or department does not exist, it will be added automatically based on your entry.
          </div>

          {/* Actions */}
          <div className="up-actions">
            <button type="submit" className="up-submit" disabled={isUploading}>
              {isUploading ? (
                <>
                  <span className="up-spin">⏳</span> Uploading...
                </>
              ) : (
                "Upload Document"
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Success Toast */}
      {successMessage && (
        <div className="up-toast">
          <div>
            <strong>Success</strong>
            <span>{successMessage}</span>
          </div>
        </div>
      )}
    </>
  );
}