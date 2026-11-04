/**
 * Service for sending files to the backend
 */
'use client';

/**
 * Sends a file to the backend server
 * @param file The file to be uploaded
 * @param endpoint The endpoint URL (defaults to '/api/upload')
 * @param additionalData Optional additional data to send with the file
 * @returns Promise with the server response
 */
export async function sendFile(
  file: File,
  endpoint: string = '/api/upload',
  additionalData?: Record<string, string | number | boolean>
): Promise<Response> {
  if (!file) {
    throw new Error('No file provided');
  }

  // Create FormData and append the file
  const formData = new FormData();
  formData.append('file', file);

  // Add any additional data if provided
  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, String(value));
    });
  }

  try {
    // Send the file to the backend
    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
      // Do not set Content-Type header, it will be set automatically with the boundary
    });

    if (!response.ok) {
      throw new Error(
        `Upload failed: ${response.status} ${response.statusText}`
      );
    }

    return response;
  } catch (error) {
    console.error('Error uploading file:', error);
    throw error;
  }
}
