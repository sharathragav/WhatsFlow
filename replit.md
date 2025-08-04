# WhatsApp Bulk Marketing Automation Platform

## Overview

This is a WhatsApp bulk messaging and marketing automation platform built with Flask and Python. The system allows users to send promotional messages to customers through WhatsApp Web automation using Selenium WebDriver. The platform provides campaign management, customer management, progress tracking, and analytics features through a modern web interface.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (August 2025)

- **Technical Issues Resolved**: Fixed all LSP diagnostics including WebDriver null checks and JavaScript duplicate declarations
- **Documentation Created**: Comprehensive DOCUMENTATION.md and README.md files created with detailed feature explanations
- **Application Status**: Fully functional with all 7 dashboards operational
- **Dependencies**: All required packages installed and verified working
- **Code Quality**: All type checking errors resolved, application running without errors

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 for responsive UI
- **JavaScript Architecture**: Vanilla JavaScript with modular class-based components
- **Styling**: Custom CSS with WhatsApp-themed design variables and Bootstrap integration
- **Components**: Modular dashboard components including progress tracking, file upload handling, and real-time updates

### Backend Architecture
- **Web Framework**: Flask with CORS support for API endpoints
- **Application Structure**: Modular design with separate WhatsApp sender package
- **Session Management**: Flask sessions with configurable secret key
- **File Handling**: Secure file uploads with validation for Excel files and attachments
- **Threading**: Background task processing for bulk message sending with progress tracking

### WhatsApp Integration
- **Automation Engine**: Selenium WebDriver with Chrome browser automation
- **Profile Management**: Uses existing Chrome user profiles to maintain WhatsApp Web sessions
- **Message Processing**: Bulk message sending with configurable delays and retry mechanisms
- **File Support**: Handles various attachment types (PDF, images, documents)

### Data Management
- **Customer Data**: Excel file processing using pandas for recipient lists
- **Mock Data Layer**: In-memory customer storage for demonstration purposes
- **File Storage**: Local file system for uploads and attachments
- **Configuration**: Environment-based configuration with fallback defaults

### Progress Tracking System
- **Real-time Monitoring**: Global progress tracking with statistics
- **Logging System**: Comprehensive logging with different message types
- **Status Updates**: Live progress updates through polling mechanism
- **Error Handling**: Success/failure counting with detailed error logs

### Security Considerations
- **File Validation**: Strict file type and size validation
- **Secure Uploads**: Werkzeug secure filename handling
- **Session Security**: Configurable session secret keys
- **Chrome Security**: Sandboxed Chrome execution with security flags

## External Dependencies

### Core Framework Dependencies
- **Flask**: Main web framework with CORS support
- **Pandas**: Excel file processing and data manipulation
- **Werkzeug**: Secure file handling utilities

### Browser Automation
- **Selenium WebDriver**: Chrome browser automation for WhatsApp Web
- **ChromeDriverManager**: Automatic Chrome driver management
- **Chrome Browser**: Requires existing Chrome installation with user profiles

### Data Processing
- **openpyxl/xlrd**: Excel file reading and writing support
- **Pillow**: Image processing for attachment handling

### Frontend Libraries (CDN)
- **Bootstrap 5**: UI framework and responsive design
- **Font Awesome**: Icon library for UI elements
- **Chart.js**: Analytics and progress visualization

### Development Tools
- **Python Logging**: Built-in logging for debugging and monitoring
- **Threading**: Built-in threading for background task processing

### System Requirements
- **Chrome Browser**: Must be installed with accessible user profile
- **File System**: Local storage for uploads and temporary files
- **Network Access**: Internet connection for WhatsApp Web and CDN resources