# Style Matcher V1: Monolithic MVP Architecture

## Vision
The initial proof-of-concept focused on creating a functional pipeline for image aesthetic transformation and background removal.

## Core Features
1. **Physical File Sorting**: The system evaluated photos for blur and exposure and physically moved them into `/Accepted` and `/Rejected` subfolders.
2. **Standard Sharpness Detection**: Used OpenCV Laplacian variance with a hard-coded threshold of 100.0.
3. **Monolithic Backend**: All API logic, image processing functions, and Pydantic models were stored in a single `main.py` file.
4. **Local Background Removal**: Integrated `@imgly/background-removal` to perform object isolation completely in the browser.
5. **Basic AI Coaching**: Implemented the first integration of Gemini/Ollama to provide feedback on camera settings based on EXIF data.

## Limitations (Addressed in V2)
- Recursive file copying was slow and risk-prone for large sessions.
- Lack of a "Gray Area" (Amber) for subjective borderline cases.
- No support for native macOS tagging or XMP sidecars.
- No zero-reference enhancement fallback.
