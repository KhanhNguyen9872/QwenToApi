import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import os
import sys
from datetime import datetime
import socket
import logging

logger = logging.getLogger(__name__)

class GUIUI:
    """GUI UI for user interaction with modern styling and functionality"""
    
    def __init__(self):
        self.root = None
        self.current_route = "No active route"
        self.current_request_body = None
        self.current_chat_id = None
        self.current_parent_id = None
        self.server_mode = None
        self.server_port = None
        self.server_running = False
        self.server_thread = None
        self.ip_address = "127.0.0.1"
        self.port = 1235  # Default port
        self.mode = "lmstudio"  # Default mode
        # Defaults
        self.ui_scale = 1.5
        self._last_scale = 1.5  # For font calculations
        self.selected_model = None
        self.cookie_value = ""
        self.bx_ua_value = ""
        self.bx_umidtoken_value = ""
        # Load persisted settings (ui_scale, ip, port, mode, selected_model)
        self._load_settings()
        self.log_lines = []
        self.max_log_lines = 100
        self.max_log_chars = 5000
        self.chat_history = []
        self.chat_id = None
        self.parent_id = None
        self.queue_size = 0
        self.processing = False
        self.queue_info = None  # Store detailed queue info from queue_manager
        self.update_queue = []
        self.update_lock = threading.Lock()
        
    def is_display_available(self):
        """Check if DISPLAY is available (for Linux systems)"""
        if sys.platform.startswith('linux'):
            return 'DISPLAY' in os.environ
        return True  # Windows and macOS always have DISPLAY

    def _setup_responsive_window(self):
        """Setup responsive window properties with configurable scaling"""
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Use the configurable UI scale (default 1.5 for Windows 150% scaling)

        # Calculate responsive window size (80% of screen, but with limits) with scaling
        base_width = min(max(int(screen_width * 0.8), 900), 1400)
        base_height = min(max(int(screen_height * 0.8), 650), 1000)

        window_width = int(base_width * self.ui_scale)
        window_height = int(base_height * self.ui_scale)

        # Ensure scaled window doesn't exceed screen size
        window_width = min(window_width, int(screen_width * 0.95))
        window_height = min(window_height, int(screen_height * 0.95))

        # Center the window
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Set minimum size with scaling (no maximum size limit)
        min_width = int(800 * self.ui_scale)
        min_height = int(600 * self.ui_scale)
        self.root.minsize(min_width, min_height)
        # Remove maxsize limit to allow full maximize

        # Make window resizable
        self.root.resizable(True, True)

        # Configure grid weights for responsive behavior
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Handle high-DPI displays
        self._setup_dpi_awareness()

        # Set default font scaling for the entire application
        self._setup_default_fonts()

    def _setup_dpi_awareness(self):
        """Setup DPI awareness for high-resolution displays"""
        try:
            # Try to enable DPI awareness on Windows
            if sys.platform == 'win32':
                try:
                    from ctypes import windll
                    windll.shcore.SetProcessDpiAwareness(1)
                except:
                    pass

            # Get DPI scaling factor
            dpi = self.root.winfo_fpixels('1i')
            scale_factor = dpi / 96.0  # 96 DPI is standard

            if scale_factor > 1.2:
                # Adjust font sizes for high DPI
                self.dpi_scale = scale_factor
                # Font sizes will be adjusted in _adjust_layout_for_size
            else:
                self.dpi_scale = 1.0

        except Exception as e:
            logger.warning(f"Could not setup DPI awareness: {e}")
            self.dpi_scale = 1.0

    def _setup_default_fonts(self):
        """Setup default fonts for the entire application with scaling"""
        try:
            import tkinter.font as tkFont

            scale = self.ui_scale

            # Set default font for the entire application
            default_font_size = int(10 * scale)
            default_font = tkFont.nametofont("TkDefaultFont")
            default_font.configure(size=default_font_size)

            # Set text font
            text_font_size = int(10 * scale)
            text_font = tkFont.nametofont("TkTextFont")
            text_font.configure(size=text_font_size)

            # Set fixed font (for code/monospace)
            fixed_font_size = int(10 * scale)
            fixed_font = tkFont.nametofont("TkFixedFont")
            fixed_font.configure(size=fixed_font_size)

            # Set menu font
            menu_font_size = int(9 * scale)
            menu_font = tkFont.nametofont("TkMenuFont")
            menu_font.configure(size=menu_font_size)

            # Set caption font (for small text)
            caption_font_size = int(8 * scale)
            caption_font = tkFont.nametofont("TkCaptionFont")
            caption_font.configure(size=caption_font_size)

            # Also set global font options for all widgets
            self.root.option_add("*Font", f"Helvetica {default_font_size}")
            self.root.option_add("*Button.Font", f"Helvetica {default_font_size}")
            self.root.option_add("*Label.Font", f"Helvetica {default_font_size}")
            self.root.option_add("*Entry.Font", f"Helvetica {default_font_size}")
            self.root.option_add("*Text.Font", f"Helvetica {default_font_size}")

            # Try to set Tk scaling (this affects all measurements)
            try:
                # This sets the scaling for all Tk measurements
                self.root.tk.call('tk', 'scaling', scale)
            except:
                pass  # Not all Tk versions support this

        except Exception as e:
            logger.warning(f"Could not setup default fonts: {e}")

    def _on_window_resize(self, event):
        """Handle window resize events for responsive behavior"""
        # Only handle resize events for the main window
        if event.widget == self.root:
            # Update wraplength for labels based on window width
            new_width = event.width
            new_height = event.height

            # Responsive text wrapping
            wrap_width = max(new_width - 150, 300)
            if hasattr(self, 'route_value'):
                self.route_value.config(wraplength=wrap_width)
            if hasattr(self, 'mode_description'):
                self.mode_description.config(wraplength=wrap_width)

            # Responsive layout adjustments based on window size
            self._adjust_layout_for_size(new_width, new_height)

                # Update status bar with version, window info, scale, and responsive indicator
            if hasattr(self, 'window_info'):
                scale_percent = int(self.ui_scale * 100)
                self.window_info.config(text=f"{new_width}x{new_height} • {scale_percent}%")

    def _adjust_layout_for_size(self, width, height):
        """Adjust layout based on window size"""
        # Small screen adjustments (< 1000px width)
        if width < 1000:
            # Make buttons smaller or stack them
            if hasattr(self, 'start_button'):
                self.start_button.config(text="Start")
                self.stop_button.config(text="Stop")
        else:
            # Normal size buttons
            if hasattr(self, 'start_button'):
                self.start_button.config(text="Start Server")
                self.stop_button.config(text="Stop Server")

        # Very small screen adjustments (< 900px width)
        if width < 900:
            # Further compress UI elements
            if hasattr(self, 'notebook'):
                # Could adjust tab text or layout here
                pass

        # Adjust font sizes for very small screens with DPI and UI scaling consideration
        base_font_size = 10

        # Apply UI scaling (1.1x)
        if hasattr(self, 'ui_scale'):
            base_font_size = int(base_font_size * self.ui_scale)

        # Apply DPI scaling
        if hasattr(self, 'dpi_scale'):
            base_font_size = int(base_font_size * self.dpi_scale)

        if width < 800:
            font_size = max(int(base_font_size * 0.8), 8)
        elif width < 1000:
            font_size = max(int(base_font_size * 0.9), 9)
        else:
            font_size = base_font_size

        # Update font sizes for text areas
        if hasattr(self, 'log_text'):
            self.log_text.config(font=('Consolas', font_size))
        if hasattr(self, 'chat_history_text'):
            self.chat_history_text.config(font=('Helvetica', font_size))
        if hasattr(self, 'routes_text'):
            self.routes_text.config(font=('Consolas', max(font_size - 1, 8)))

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for better UX"""
        # Ctrl+S to start server
        self.root.bind('<Control-s>', lambda e: self._start_server())

        # Ctrl+Q to stop server
        self.root.bind('<Control-q>', lambda e: self._stop_server())

        # Ctrl+N for new chat
        self.root.bind('<Control-n>', lambda e: self._create_new_chat())

        # Ctrl+M to show models
        self.root.bind('<Control-m>', lambda e: self._show_models())

        # Ctrl+R to show routes
        self.root.bind('<Control-r>', lambda e: self._show_routes())

        # F1 for help/about
        self.root.bind('<F1>', lambda e: self._show_help())

        # F5 to refresh/update status
        self.root.bind('<F5>', lambda e: self._update_status())

        # Escape to close focused popup windows
        self.root.bind('<Escape>', self._handle_escape)

    def _handle_escape(self, event):
        """Handle escape key to close popup windows"""
        # Get the focused widget
        focused = self.root.focus_get()
        if focused:
            # Check if it's in a Toplevel window
            toplevel = focused.winfo_toplevel()
            if toplevel != self.root and isinstance(toplevel, tk.Toplevel):
                toplevel.destroy()

    def _show_help(self):
        """Show help dialog with keyboard shortcuts"""
        help_text = """🎯 Keyboard Shortcuts:

Ctrl+S    - Start Server
Ctrl+Q    - Stop Server
Ctrl+N    - New Chat
Ctrl+M    - Show Models
Ctrl+R    - Show Routes
F1        - Show this help
F2        - Show About
F5        - Refresh status
Escape    - Close popup windows

🖱️  Mouse Controls:
- Resize window by dragging edges
- All text areas are scrollable
- Tabs can be clicked to switch views
- Buttons have hover effects

🔧 Features:
- Auto-responsive layout
- Thread-safe UI updates
- Real-time server monitoring
- Queue management display"""

        self._show_help_window(help_text)

    def _setup_window_state_management(self):
        """Setup window state management for better responsiveness"""
        # Handle window state changes (minimize, maximize, restore)
        self.root.bind('<Map>', self._on_window_map)
        self.root.bind('<Unmap>', self._on_window_unmap)

        # Set window icon if available
        try:
            icon_path = self._get_icon_path()
            if icon_path and os.path.exists(icon_path):
                # Try iconbitmap first (Windows)
                try:
                    self.root.iconbitmap(icon_path)
                    logger.info(f"Window icon set: {icon_path}")
                except:
                    # Fallback for other platforms
                    try:
                        self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
                        logger.info(f"Window icon set (photo): {icon_path}")
                    except:
                        logger.warning(f"Could not set window icon with photo method")
            else:
                logger.warning(f"Icon file not found: {icon_path}")
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}")

        # Make window appear in taskbar properly
        self.root.lift()
        self.root.attributes('-topmost', False)

        # Center window on screen initially
        self.root.update_idletasks()
    
    def _setup_window_close_handler(self):
        """Setup window close handler with server confirmation"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
    
    def _on_window_close(self):
        """Handle window close event with server confirmation"""
        if self.server_running:
            # Show confirmation dialog when server is running
            result = messagebox.askyesno(
                "Close Application",
                "The server is currently running.\n\n"
                f"Server: {self.ip_address}:{self.port}\n"
                f"Mode: {self.mode}\n\n"
                "Do you want to stop the server and close the application?\n\n"
                "Press 'Yes' to stop server and close, or 'No' to keep running.",
                icon='warning'
            )
            
            if result:
                # User confirmed - stop server and close
                try:
                    import main as _server
                    _server.stop_embedded()
                except Exception as e:
                    logger.warning(f"Error stopping server on close: {e}")
                
                self.server_running = False
                self.root.destroy()
            else:
                # User cancelled - don't close
                return
        
        # Server not running or user confirmed - close normally
        self.root.destroy()

    def _on_window_map(self, event):
        """Handle window being mapped (shown/restored)"""
        if event.widget == self.root:
            # Window is being shown/restored
            self._update_status()

    def _on_window_unmap(self, event):
        """Handle window being unmapped (minimized/hidden)"""
        if event.widget == self.root:
            # Window is being minimized/hidden
            # Could pause updates here if needed
            pass

    def _create_status_bar(self, parent):
        """Create a responsive status bar with scaling"""
        status_bar = ttk.Frame(parent, style='Header.TFrame')
        status_bar.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        status_bar.grid_columnconfigure(1, weight=1)

        # Calculate scaled font size
        scale = getattr(self, 'ui_scale', 1.5)
        status_font_size = int(9 * scale)  # Slightly larger for better visibility

        # Left side - connection info
        self.connection_status = ttk.Label(status_bar,
                                         text="Stopped",
                                         foreground="white",
                                         background=self.colors['secondary'],
                                         font=('Helvetica', status_font_size))
        self.connection_status.grid(row=0, column=0, padx=int(8 * scale), pady=int(3 * scale), sticky="w")

        # Middle - server status
        self.server_status = ttk.Label(status_bar,
                                     text="Server: Stopped",
                                     foreground="white",
                                     background=self.colors['secondary'],
                                     font=('Helvetica', status_font_size))
        self.server_status.grid(row=0, column=1, padx=int(8 * scale), pady=int(3 * scale))

        # Right side - version and window size info
        try:
            from config import VERSION
            version_text = f"v{VERSION}"
        except ImportError:
            version_text = "v1.0.1"
            
        self.window_info = ttk.Label(status_bar,
                                   text=f"{version_text}",
                                   foreground="white",
                                   background=self.colors['secondary'],
                                   font=('Helvetica', status_font_size))
        self.window_info.grid(row=0, column=2, padx=int(8 * scale), pady=int(3 * scale), sticky="e")

    def _on_window_map(self, event):
        """Handle window being mapped (shown/restored)"""
        if event.widget == self.root:
            # Window is being shown/restored
            self._update_status()

    def _on_window_unmap(self, event):
        """Handle window being unmapped (minimized/hidden)"""
        if event.widget == self.root:
            # Window is being minimized/hidden
            # Could pause updates here if needed
            pass

    def initialize(self):
        """Initialize the GUI interface without starting the main loop"""
        if not self.is_display_available():
            logger.warning("DISPLAY not available, falling back to terminal UI")
            return False

        self.root = tk.Tk()
        
        # Set window title with version
        try:
            from config import VERSION
            self.root.title(f"QwenToApi | KhanhNguyen9872")
        except ImportError:
            self.root.title("QwenToApi | KhanhNguyen9872")

        # Make window responsive (this loads the UI scale)
        self._setup_responsive_window()

        # Setup default fonts with scaling
        self._setup_default_fonts()

        # Set up modern styling
        self._setup_styles()

        # Pre-fill settings to entries once widgets exist
        # Create the main layout
        self._create_widgets()

        # After widgets created, push loaded settings to UI controls
        try:
            if hasattr(self, 'ip_entry'):
                self.ip_entry.delete(0, tk.END)
                self.ip_entry.insert(0, self.ip_address)
            if hasattr(self, 'port_entry'):
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, str(self.port))
            if hasattr(self, 'mode_var') and self.mode:
                self.mode_var.set(self.mode)
            if hasattr(self, 'scale_var'):
                self.scale_var.set(f"{int(self.ui_scale * 100)}%")
        except Exception as e:
            logger.warning(f"Could not apply loaded settings to UI: {e}")

        # Start the update loop
        self._start_update_loop()

        # Initialize status bar
        self._update_server_status()

        # Bind events for responsive behavior
        self.root.bind('<Configure>', self._on_window_resize)

        # Add keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Setup window state management
        self._setup_window_state_management()
        
        # Setup window close handler
        self._setup_window_close_handler()

        return True

    def run_main_loop(self):
        """Run the GUI main loop in the main thread"""
        if not self.root:
            logger.error("GUI not initialized. Call initialize() first.")
            return False

        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in GUI main loop: {e}")
            return False

        return True

    def start(self):
        """Start the GUI interface (legacy method for compatibility)"""
        if self.initialize():
            return self.run_main_loop()
        return False
    
    def _setup_styles(self):
        """Set up modern styling for the GUI with 1.1x scaling"""
        style = ttk.Style()

        # Configure base styles
        style.theme_use('clam')

        # Get scaling factor
        scale = getattr(self, 'ui_scale', 1.1)

        # Colors
        self.colors = {
            'primary': '#3498db',
            'primary_dark': '#2980b9',
            'secondary': '#2c3e50',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#2c3e50',
            'border': '#bdc3c7'
        }
        
        # Frame styling
        style.configure('Main.TFrame', background=self.colors['light'])
        style.configure('Card.TFrame', 
                        background='white',
                        borderwidth=1,
                        relief='solid',
                        bordercolor=self.colors['border'])
        style.configure('Header.TFrame', 
                        background=self.colors['secondary'],
                        borderwidth=0)
        
        # Button styling with scaling
        button_padding = (int(10 * scale), int(5 * scale))
        button_font_size = int(10 * scale)
        button_width = int(12 * scale)  # Default button width

        style.configure('Primary.TButton',
                        background=self.colors['primary'],
                        foreground='white',
                        borderwidth=0,
                        padding=button_padding,
                        font=('Helvetica', button_font_size),
                        width=button_width)
        style.map('Primary.TButton',
                 background=[('active', self.colors['primary_dark'])])

        style.configure('Secondary.TButton',
                        background=self.colors['secondary'],
                        foreground='white',
                        borderwidth=0,
                        padding=button_padding,
                        font=('Helvetica', button_font_size),
                        width=button_width)
        style.map('Secondary.TButton',
                 background=[('active', '#1a252f')])

        style.configure('Success.TButton',
                        background=self.colors['success'],
                        foreground='white',
                        borderwidth=0,
                        padding=button_padding,
                        font=('Helvetica', button_font_size),
                        width=button_width)
        style.map('Success.TButton',
                 background=[('active', '#27ae60')])

        style.configure('Danger.TButton',
                        background=self.colors['danger'],
                        foreground='white',
                        borderwidth=0,
                        padding=button_padding,
                        font=('Helvetica', button_font_size),
                        width=button_width)
        style.map('Danger.TButton',
                 background=[('active', '#c0392b')])
        
        # Label styling with scaling
        header_font_size = int(14 * scale)
        card_header_font_size = int(12 * scale)
        status_font_size = int(10 * scale)
        route_font_size = int(10 * scale)
        header_padding = int(10 * scale)
        card_padding = (int(10 * scale), int(5 * scale))
        route_wraplength = int(800 * scale)

        style.configure('Header.TLabel',
                        background=self.colors['secondary'],
                        foreground='white',
                        font=('Helvetica', header_font_size, 'bold'),
                        padding=header_padding)
        style.configure('CardHeader.TLabel',
                        background='white',
                        foreground=self.colors['dark'],
                        font=('Helvetica', card_header_font_size, 'bold'),
                        padding=card_padding)
        style.configure('Status.TLabel',
                        font=('Helvetica', status_font_size))
        style.configure('Route.TLabel',
                        font=('Consolas', route_font_size),
                        wraplength=route_wraplength)
        
        # Entry styling with scaling
        entry_padding = int(5 * scale)
        entry_font_size = int(10 * scale)

        style.configure('TEntry',
                        fieldbackground='white',
                        borderwidth=1,
                        relief='solid',
                        bordercolor=self.colors['border'],
                        padding=entry_padding,
                        font=('Helvetica', entry_font_size))

        # Combobox styling with scaling
        style.configure('TCombobox',
                        fieldbackground='white',
                        borderwidth=1,
                        relief='solid',
                        bordercolor=self.colors['border'],
                        padding=entry_padding,
                        font=('Helvetica', entry_font_size))

        # Notebook/Tab styling with scaling
        tab_padding = [int(12 * scale), int(8 * scale)]  # Increased padding for better scaling
        tab_font_size = int(10 * scale)
        tab_height = int(30 * scale)  # Explicit tab height

        style.configure('TNotebook',
                        background=self.colors['light'],
                        borderwidth=0,
                        tabmargins=[2, 5, 2, 0])  # Add margins for better appearance
        style.configure('TNotebook.Tab',
                        background=self.colors['light'],
                        foreground=self.colors['dark'],
                        padding=tab_padding,
                        font=('Helvetica', tab_font_size),
                        focuscolor='none')  # Remove focus outline
        style.map('TNotebook.Tab',
                 background=[('selected', 'white')],
                 foreground=[('selected', self.colors['primary'])])

        # Additional widget styling with scaling
        widget_font_size = int(9 * scale)

        # Checkbutton styling
        style.configure('TCheckbutton',
                        font=('Helvetica', widget_font_size))

        # Radiobutton styling
        style.configure('TRadiobutton',
                        font=('Helvetica', widget_font_size))

        # Scale styling
        style.configure('TScale',
                        font=('Helvetica', widget_font_size))

        # Progressbar height scaling
        progressbar_height = int(20 * scale)
        style.configure('TProgressbar',
                        thickness=progressbar_height)
    
    def _create_widgets(self):
        """Create all GUI widgets with responsive layout"""
        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Main container using grid for better control
        main_frame = ttk.Frame(self.root, style='Main.TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Configure main frame grid
        main_frame.grid_rowconfigure(1, weight=1)  # Notebook gets most space
        main_frame.grid_columnconfigure(0, weight=1)

        # Add responsive status bar
        self._create_status_bar(main_frame)

        # Header
        header_frame = ttk.Frame(main_frame, style='Header.TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)  # Space between title and status

        # Import version from config
        try:
            from config import VERSION
            version_text = f"QwenToApi v{VERSION} | KhanhNguyen9872"
        except ImportError:
            version_text = "QwenToApi | KhanhNguyen9872"
            
        ttk.Label(header_frame,
                 text=version_text,
                 style='Header.TLabel').grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.status_label = ttk.Label(header_frame,
                                     text="Server Status: Stopped",
                                     foreground="white",
                                     background=self.colors['secondary'],
                                     font=('Helvetica', 10))
        self.status_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")

        # Create tab control with responsive sizing
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        # Create tabs
        self._create_main_tab()
        self._create_logs_tab()
        self._create_settings_tab()

        # Control panel
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        
        # Server control buttons (left side)
        server_frame = ttk.Frame(control_frame)
        server_frame.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.start_button = ttk.Button(server_frame,
                                     text="Start Server",
                                     style='Success.TButton',
                                     command=self._start_server)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(server_frame,
                                    text="Stop Server",
                                    style='Danger.TButton',
                                    command=self._stop_server,
                                    state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        # Action buttons (right side)
        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=0, column=1, sticky="e")

        ttk.Button(action_frame,
                  text="Show Models",
                  style='Primary.TButton',
                  command=self._show_models).grid(row=0, column=0, padx=5)

        ttk.Button(action_frame,
                  text="Show Routes",
                  style='Primary.TButton',
                  command=self._show_routes).grid(row=0, column=1, padx=5)

        ttk.Button(action_frame,
                  text="About",
                  style='Secondary.TButton',
                  command=self._show_about).grid(row=0, column=2, padx=5)

    def _create_main_tab(self):
        """Create the main tab with server status and route info"""
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="Dashboard")

        # Configure main tab grid
        main_tab.grid_rowconfigure(1, weight=1)  # Route section gets extra space
        main_tab.grid_columnconfigure(0, weight=1)

        # Server status card
        status_card = ttk.Frame(main_tab, style='Card.TFrame')
        status_card.grid(row=0, column=0, sticky="ew", pady=5, padx=10)
        status_card.grid_columnconfigure(0, weight=1)

        ttk.Label(status_card,
                 text="🖥️ Server Status",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Server info using responsive grid
        info_frame = ttk.Frame(status_card)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        info_frame.grid_columnconfigure(1, weight=1)
        info_frame.grid_columnconfigure(3, weight=1)

        # Calculate font sizes for status labels
        scale = getattr(self, 'ui_scale', 1.1)
        status_font_size = int(10 * scale)

        # First row: Status and Mode
        ttk.Label(info_frame, text="⚙️ Status:", font=('Helvetica', status_font_size)).grid(row=0, column=0, sticky="w", padx=5)
        self.server_status_value = ttk.Label(info_frame, text="Stopped", foreground=self.colors['danger'], font=('Helvetica', status_font_size))
        self.server_status_value.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(info_frame, text="🧭 Mode:", font=('Helvetica', status_font_size)).grid(row=0, column=2, sticky="w", padx=15)
        self.server_mode_value = ttk.Label(info_frame, text="Not set", font=('Helvetica', status_font_size))
        self.server_mode_value.grid(row=0, column=3, sticky="w", padx=5)

        # Second row: Port and Host
        ttk.Label(info_frame, text="🔌 Port:", font=('Helvetica', status_font_size)).grid(row=1, column=0, sticky="w", padx=5)
        self.server_port_value = ttk.Label(info_frame, text="Not set", font=('Helvetica', status_font_size))
        self.server_port_value.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(info_frame, text="🌐 Host:", font=('Helvetica', status_font_size)).grid(row=1, column=2, sticky="w", padx=15)
        self.server_host_value = ttk.Label(info_frame, text="Not set", font=('Helvetica', status_font_size))
        self.server_host_value.grid(row=1, column=3, sticky="w", padx=5)

        # Current route card
        route_card = ttk.Frame(main_tab, style='Card.TFrame')
        route_card.grid(row=1, column=0, sticky="nsew", pady=10, padx=10)
        route_card.grid_rowconfigure(1, weight=1)
        route_card.grid_columnconfigure(0, weight=1)

        ttk.Label(route_card,
                 text="📍 Current Route & 📦 Request",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Route and request body display with scrollable text
        self.route_text = scrolledtext.ScrolledText(route_card,
                                                   wrap=tk.WORD,
                                                   font=('Consolas', int(10 * getattr(self, 'ui_scale', 1.1))),
                                                   state=tk.DISABLED,
                                                   height=8,  # Increased height for request body
                                                   bg='#f8f9fa',
                                                   fg='#2c3e50')
        self.route_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Initialize with current route info
        self._update_route_display()
        
        # Queue status card
        queue_card = ttk.Frame(main_tab, style='Card.TFrame')
        queue_card.grid(row=2, column=0, sticky="ew", pady=5, padx=10)
        queue_card.grid_columnconfigure(0, weight=1)

        ttk.Label(queue_card,
                 text="🕒 Queue Status",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        queue_info_frame = ttk.Frame(queue_card)
        queue_info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        ttk.Label(queue_info_frame, text="⚙️ Status:", font=('Helvetica', status_font_size)).grid(row=0, column=0, sticky="w", padx=5)

        self.queue_status = ttk.Label(queue_info_frame,
                                     text="Idle",
                                     foreground=self.colors['success'],
                                     font=('Helvetica', status_font_size))
        self.queue_status.grid(row=0, column=1, sticky="w", padx=5)

        self.queue_size_label = ttk.Label(queue_info_frame,
                                        text="📨 (0 requests)",
                                        foreground=self.colors['secondary'],
                                        font=('Helvetica', status_font_size))
        self.queue_size_label.grid(row=0, column=2, sticky="w", padx=5)

        # Chat controls moved here
        chat_ctrl_card = ttk.Frame(main_tab, style='Card.TFrame')
        chat_ctrl_card.grid(row=3, column=0, sticky="ew", pady=5, padx=10)
        chat_ctrl_card.grid_columnconfigure(3, weight=1)

        ttk.Label(chat_ctrl_card,
                 text="💬 Chat Controls",
                 style='CardHeader.TLabel').grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=5)

        ttk.Label(chat_ctrl_card, text="🆔 Chat ID:", font=('Helvetica', status_font_size)).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.chat_id_value = ttk.Label(chat_ctrl_card, text="Not initialized", font=('Helvetica', status_font_size))
        self.chat_id_value.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(chat_ctrl_card, text="🧩 Parent ID:", font=('Helvetica', status_font_size)).grid(row=1, column=2, sticky="e", padx=10, pady=5)
        self.parent_id_value = ttk.Label(chat_ctrl_card, text="None", font=('Helvetica', status_font_size))
        self.parent_id_value.grid(row=1, column=3, sticky="w", padx=5)

        ttk.Button(chat_ctrl_card,
                  text="✨ New Chat",
                  style='Secondary.TButton',
                  command=self._create_new_chat).grid(row=1, column=4, sticky="e", padx=10)
    
    def _create_logs_tab(self):
        """Create the logs tab with log viewer"""
        logs_tab = ttk.Frame(self.notebook)
        self.notebook.add(logs_tab, text="Logs")

        # Configure logs tab grid
        logs_tab.grid_rowconfigure(0, weight=1)
        logs_tab.grid_columnconfigure(0, weight=1)

        # Log viewer card
        log_frame = ttk.Frame(logs_tab, style='Card.TFrame')
        log_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(log_frame,
                 text="Server Logs",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Log text area with responsive sizing
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                wrap=tk.WORD,
                                                font=('Consolas', 10),
                                                state=tk.DISABLED,
                                                bg='#1e1e1e',
                                                fg='white')
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Log controls
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        log_control_frame.grid_columnconfigure(0, weight=1)

        ttk.Button(log_control_frame,
                  text="Clear Logs",
                  style='Secondary.TButton',
                  command=self._clear_logs).grid(row=0, column=1, sticky="e", padx=5)
    
    def _create_settings_tab(self):
        """Create the settings tab for configuration"""
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="Settings")

        # Configure settings tab grid
        settings_tab.grid_rowconfigure(1, weight=1)  # Routes card gets extra space
        settings_tab.grid_columnconfigure(0, weight=1)

        # Configuration card
        config_card = ttk.Frame(settings_tab, style='Card.TFrame')
        config_card.grid(row=0, column=0, sticky="ew", pady=10, padx=10)
        config_card.grid_columnconfigure(0, weight=1)

        ttk.Label(config_card,
                 text="Server Configuration",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Configuration content frame
        config_content = ttk.Frame(config_card)
        config_content.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        config_content.grid_columnconfigure(1, weight=1)

        # IP and Port configuration using responsive grid
        scale = getattr(self, 'ui_scale', 1.1)
        entry_font_size = int(10 * scale)
        label_font_size = int(10 * scale)
        
        ttk.Label(config_content, text="IP Address:", font=('Helvetica', label_font_size)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.ip_entry = ttk.Entry(config_content, width=20, font=('Helvetica', entry_font_size))
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.ip_entry.insert(0, self.ip_address)

        ttk.Label(config_content, text="Port:", font=('Helvetica', label_font_size)).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.port_entry = ttk.Entry(config_content, width=10, font=('Helvetica', entry_font_size))
        self.port_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.port_entry.insert(0, str(self.port))

        # Server mode with responsive layout
        ttk.Label(config_content, text="Server Mode:", font=('Helvetica', label_font_size)).grid(row=2, column=0, sticky="w", padx=5, pady=5)

        mode_control_frame = ttk.Frame(config_content)
        mode_control_frame.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        mode_control_frame.grid_columnconfigure(0, weight=1)

        self.mode_var = tk.StringVar(value=self.mode)
        mode_combo = ttk.Combobox(mode_control_frame,
                                 textvariable=self.mode_var,
                                 values=["lmstudio", "ollama"],
                                 state="readonly",
                                 width=15,
                                 font=('Helvetica', entry_font_size))
        mode_combo.grid(row=0, column=0, sticky="w", padx=5)
        mode_combo.bind('<<ComboboxSelected>>', self._on_mode_changed)

        # Auto-set port button
        ttk.Button(mode_control_frame,
                  text="Auto-set Port",
                  style='Secondary.TButton',
                  command=self._auto_set_port).grid(row=0, column=1, sticky="w", padx=10)

        # UI Scale setting
        ttk.Label(config_content, text="UI Scale:", font=('Helvetica', label_font_size)).grid(row=3, column=0, sticky="w", padx=5, pady=5)

        scale_control_frame = ttk.Frame(config_content)
        scale_control_frame.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        scale_control_frame.grid_columnconfigure(0, weight=1)

        self.scale_var = tk.StringVar(value=f"{int(self.ui_scale * 100)}%")
        scale_combo = ttk.Combobox(scale_control_frame,
                                  textvariable=self.scale_var,
                                  values=["100%", "110%", "125%", "150%", "175%", "200%"],
                                  state="readonly",
                                  width=8,
                                  font=('Helvetica', entry_font_size))
        scale_combo.grid(row=0, column=0, sticky="w", padx=5)
        scale_combo.bind('<<ComboboxSelected>>', self._on_scale_changed)

        # Scale description
        self.scale_description = ttk.Label(config_content,
                                          text=f"Current: {int(self.ui_scale * 100)}% - Adjusts all UI elements size",
                                          font=('Helvetica', int(8 * scale)),
                                          foreground=self.colors['secondary'])
        self.scale_description.grid(row=3, column=2, sticky="w", padx=10, pady=5)

        # Mode description
        self.mode_description = ttk.Label(config_card,
                                         text=self._get_mode_description(),
                                         font=('Helvetica', int(9 * scale)),
                                         foreground=self.colors['secondary'],
                                         wraplength=700,
                                         justify="left")
        self.mode_description.grid(row=4, column=0, sticky="ew", padx=10, pady=5)

        # Cookie input card (replaces Available API Routes)
        cookie_card = ttk.Frame(settings_tab, style='Card.TFrame')
        cookie_card.grid(row=1, column=0, sticky="nsew", pady=10, padx=10)
        cookie_card.grid_rowconfigure(1, weight=1)
        cookie_card.grid_columnconfigure(0, weight=1)

        ttk.Label(cookie_card,
                 text="Qwen Cookie (JSON array)",
                 style='CardHeader.TLabel').grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.cookie_text = scrolledtext.ScrolledText(cookie_card,
                                                    wrap=tk.WORD,
                                                    font=('Consolas', int(9 * scale)))
        self.cookie_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Prefill cookie from settings
        try:
            if self.cookie_value:
                self.cookie_text.insert(tk.END, self.cookie_value)
        except Exception:
            pass

        # Optional anti-bot headers (bx-ua, bx-umidtoken) - not required
        bx_card = ttk.Frame(settings_tab, style='Card.TFrame')
        bx_card.grid(row=2, column=0, sticky="ew", pady=10, padx=10)
        bx_card.grid_columnconfigure(1, weight=1)
        ttk.Label(bx_card, text="Optional request headers (only sent when set)",
                  style='CardHeader.TLabel').grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        ttk.Label(bx_card, text="bx-ua:", font=('Helvetica', int(9 * scale))).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.bx_ua_entry = ttk.Entry(bx_card, font=('Consolas', int(9 * scale)), width=60)
        self.bx_ua_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        if getattr(self, 'bx_ua_value', ''):
            self.bx_ua_entry.insert(0, self.bx_ua_value)
        ttk.Label(bx_card, text="bx-umidtoken:", font=('Helvetica', int(9 * scale))).grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.bx_umidtoken_entry = ttk.Entry(bx_card, font=('Consolas', int(9 * scale)), width=60)
        self.bx_umidtoken_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        if getattr(self, 'bx_umidtoken_value', ''):
            self.bx_umidtoken_entry.insert(0, self.bx_umidtoken_value)

        # Save button moved to bottom of Settings tab
        bottom_save_frame = ttk.Frame(settings_tab)
        bottom_save_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_save_frame.grid_columnconfigure(0, weight=1)

        # Refresh Model Cache button
        ttk.Button(bottom_save_frame,
                  text="🔄 Refresh Model",
                  style='Secondary.TButton',
                  command=self._refresh_model_cache).grid(row=0, column=0, sticky="w", padx=5)

        ttk.Button(bottom_save_frame,
                  text="Save",
                  style='Primary.TButton',
                  command=self._apply_configuration).grid(row=0, column=1, sticky="e", padx=5)
    
    # Chat tab removed per requirement
    def _start_update_loop(self):
        """Start the periodic update loop"""
        def update():
            if self.root and self.root.winfo_exists():
                self._process_update_queue()
                self._update_status()
                self.root.after(1000, update)

        self.root.after(1000, update)

    def _process_update_queue(self):
        """Process any queued updates from other threads"""
        with self.update_lock:
            while self.update_queue:
                update_type, data = self.update_queue.pop(0)
                if update_type == 'route':
                    if isinstance(data, tuple) and len(data) == 2:
                        # New format with request body
                        self.current_route, self.current_request_body = data
                    else:
                        # Legacy format, just route info
                        self.current_route = data
                        self.current_request_body = None
                elif update_type == 'chat_id':
                    self.current_chat_id = data
                elif update_type == 'parent_id':
                    self.current_parent_id = data
                elif update_type == 'server_info':
                    self.server_mode, self.server_port = data
                elif update_type == 'queue_status':
                    try:
                        if len(data) == 3:
                            self.processing, self.queue_size, queue_info = data
                            # Store detailed queue info for display
                            self.queue_info = queue_info
                        else:
                            self.processing, self.queue_size = data
                            self.queue_info = None
                    except Exception:
                        pass

    def update_route(self, route_info, request_body=None):
        """Thread-safe method to update route info and request body"""
        with self.update_lock:
            self.update_queue.append(('route', (route_info, request_body)))

    def update_chat_id(self, chat_id):
        """Thread-safe method to update chat ID"""
        with self.update_lock:
            self.update_queue.append(('chat_id', chat_id))

    def update_parent_id(self, parent_id):
        """Thread-safe method to update parent ID"""
        with self.update_lock:
            self.update_queue.append(('parent_id', parent_id))

    def update_server_info(self, mode, port):
        """Thread-safe method to update server info"""
        with self.update_lock:
            self.update_queue.append(('server_info', (mode, port)))
    
    def update_queue_status(self, processing, queue_size):
        """Thread-safe method to update queue status"""
        with self.update_lock:
            # Get detailed queue status from queue_manager
            try:
                from utils.queue_manager import queue_manager
                queue_info = queue_manager.get_status()
                self.update_queue.append(('queue_status', (processing, queue_size, queue_info)))
            except Exception as e:
                logger.error(f"Error getting queue status: {e}")
                self.update_queue.append(('queue_status', (processing, queue_size, None)))
    
    def _update_status(self):
        """Update the status display"""
        # Update server status
        if self.server_running:
            self.server_status_value.config(text="Running", foreground=self.colors['success'])
            self.status_label.config(text="Server Status: Running", 
                                   foreground="white",
                                   background=self.colors['success'])
            self.server_status_value.config(foreground=self.colors['success'])
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.server_status_value.config(text="Stopped", foreground=self.colors['danger'])
            self.status_label.config(text="Server Status: Stopped", 
                                   foreground="white",
                                   background=self.colors['secondary'])
            self.server_status_value.config(foreground=self.colors['danger'])
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        
        # Update mode and port from current UI selections if available
        try:
            current_mode = self.mode_var.get() if hasattr(self, 'mode_var') else self.mode
        except Exception:
            current_mode = self.mode
        try:
            current_port = int(self.port_entry.get().strip()) if hasattr(self, 'port_entry') else self.port
        except Exception:
            current_port = self.port

        self.server_mode_value.config(text=current_mode or "Not set")
        self.server_port_value.config(text=str(current_port) if current_port else "Not set")
        
        # Update host display with saved IP address
        try:
            current_ip = self.ip_entry.get().strip() if hasattr(self, 'ip_entry') else self.ip_address
        except Exception:
            current_ip = self.ip_address
        if hasattr(self, 'server_host_value'):
            self.server_host_value.config(text=current_ip or "Not set")

        # Update status bar
        self._update_server_status()
        
        # Update route and request body display
        self._update_route_display()

        # Update chat information
        if hasattr(self, 'chat_id_value'):
            self.chat_id_value.config(text=self.current_chat_id or "Not initialized")
        if hasattr(self, 'parent_id_value'):
            self.parent_id_value.config(text=self.current_parent_id or "None")

        # Update queue status with detailed information from queue_manager
        if hasattr(self, 'queue_info') and self.queue_info:
            # Use detailed queue info from queue_manager
            queue_info = self.queue_info
            current_processing = queue_info.get('current_processing', False)
            queue_size = queue_info.get('queue_size', 0)
            lock_info = queue_info.get('lock_info', {})
            
            # Status text with processing duration if available
            if current_processing:
                processing_duration = lock_info.get('duration_seconds', 0)
                if processing_duration > 0:
                    status_text = f"Processing ({processing_duration:.1f}s)"
                else:
                    status_text = "Processing"
                color = self.colors['warning']
            else:
                status_text = "Idle"
                color = self.colors['success']
            
            # Queue size with detailed info
            if queue_size > 0:
                queue_items = queue_info.get('queue_items', [])
                if queue_items:
                    # Show first few items in queue
                    first_item = queue_items[0]
                    model = first_item.get('model', 'unknown')
                    stream = first_item.get('stream', False)
                    stream_text = " (stream)" if stream else ""
                    queue_text = f"📨 ({queue_size} requests) - Next: {model}{stream_text}"
                else:
                    queue_text = f"📨 ({queue_size} requests)"
            else:
                queue_text = "📨 (0 requests)"
        else:
            # Fallback to simple status
            status_text = "Processing" if self.processing else "Idle"
            color = self.colors['warning'] if self.processing else self.colors['success']
            queue_text = f"📨 ({self.queue_size} requests)"
        
        self.queue_status.config(text=status_text, foreground=color)
        self.queue_size_label.config(text=queue_text)

        # Update server status in status bar
        self._update_server_status()

    def _update_route_display(self):
        """Update the route and request body display with syntax highlighting"""
        if not hasattr(self, 'route_text'):
            return

        # Check if content has actually changed to avoid unnecessary updates
        current_content = f"{self.current_route}|{str(self.current_request_body)}"
        if hasattr(self, '_last_route_content') and self._last_route_content == current_content:
            return  # No change, don't update
        
        # Store current content for next comparison
        self._last_route_content = current_content

        # Enable editing temporarily
        self.route_text.config(state=tk.NORMAL)
        self.route_text.delete(1.0, tk.END)

        # Configure text tags for syntax highlighting
        self.route_text.tag_configure("route_header", foreground="#2980b9", font=('Consolas', int(10 * getattr(self, 'ui_scale', 1.1)), 'bold'))
        self.route_text.tag_configure("body_header", foreground="#27ae60", font=('Consolas', int(10 * getattr(self, 'ui_scale', 1.1)), 'bold'))
        self.route_text.tag_configure("json_key", foreground="#8e44ad")
        self.route_text.tag_configure("json_string", foreground="#d35400")
        self.route_text.tag_configure("json_number", foreground="#c0392b")

        # Add route information with highlighting
        route_start = self.route_text.index(tk.INSERT)
        self.route_text.insert(tk.END, f"📍 Route: {self.current_route}\n")
        route_end = self.route_text.index(tk.INSERT)
        self.route_text.tag_add("route_header", route_start, route_end)

        # Add request body if available
        if self.current_request_body:
            body_header_start = self.route_text.index(tk.INSERT)
            self.route_text.insert(tk.END, "\n📦 Request Body:\n")
            body_header_end = self.route_text.index(tk.INSERT)
            self.route_text.tag_add("body_header", body_header_start, body_header_end)

            if isinstance(self.current_request_body, dict):
                import json
                try:
                    # Create a copy to modify for display
                    display_body = self._prepare_request_body_for_display(self.current_request_body)
                    formatted_body = json.dumps(display_body, indent=2, ensure_ascii=False)
                    self.route_text.insert(tk.END, formatted_body)

                    # Simple JSON syntax highlighting
                    self._apply_json_highlighting()

                except:
                    self.route_text.insert(tk.END, str(self.current_request_body))
            else:
                self.route_text.insert(tk.END, str(self.current_request_body))
        else:
            body_header_start = self.route_text.index(tk.INSERT)
            self.route_text.insert(tk.END, "\n📦 Request Body: None")
            body_header_end = self.route_text.index(tk.INSERT)
            self.route_text.tag_add("body_header", body_header_start, body_header_end)

        # Disable editing
        self.route_text.config(state=tk.DISABLED)

        # Keep current scroll position - never force scroll to top
        # This prevents the annoying auto-scroll behavior
        pass

    def _prepare_request_body_for_display(self, request_body):
        """Prepare request body for display by shortening image data"""
        import copy
        
        # Create a deep copy to avoid modifying the original
        display_body = copy.deepcopy(request_body)
        
        # Process messages array if it exists
        if 'messages' in display_body and isinstance(display_body['messages'], list):
            for message in display_body['messages']:
                if isinstance(message, dict) and 'images' in message:
                    images = message['images']
                    if isinstance(images, list):
                        # Replace image data with [image1, image2, ...]
                        image_count = len(images)
                        if image_count == 1:
                            message['images'] = ['[image1]']
                        else:
                            message['images'] = [f'[image{i+1}]' for i in range(image_count)]
        
        return display_body

    def _update_server_status(self):
        """Update server status in the status bar"""
        try:
            if hasattr(self, 'server_status'):
                # Check if server is running by trying to import and check
                try:
                    from main import app
                    # Simple check - if we can import, assume server code is available
                    # Prefer current UI selections to avoid mode desync
                    try:
                        mode = self.mode_var.get() if hasattr(self, 'mode_var') else getattr(self, 'mode', 'lmstudio')
                    except Exception:
                        mode = getattr(self, 'mode', 'lmstudio')
                    try:
                        port = int(self.port_entry.get().strip()) if hasattr(self, 'port_entry') else getattr(self, 'port', 1235)
                    except Exception:
                        port = getattr(self, 'port', 1235)

                    # Try to determine if server is actually running
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.1)
                    # Use saved IP address for connection check
                    check_ip = getattr(self, 'ip_address', '127.0.0.1')
                    result = sock.connect_ex((check_ip, port))
                    sock.close()

                    if result == 0:
                        # Server is running
                        self.server_status.config(text=f"🟢 Server: Running ({mode.upper()}:{port})")
                    else:
                        # Server is not running
                        self.server_status.config(text=f"🔴 Server: Stopped ({mode.upper()}:{port})")

                except ImportError:
                    self.server_status.config(text="⚪ Server: Not Available")
                except Exception:
                    try:
                        mode = self.mode_var.get() if hasattr(self, 'mode_var') else getattr(self, 'mode', 'lmstudio')
                    except Exception:
                        mode = getattr(self, 'mode', 'lmstudio')
                    try:
                        port = int(self.port_entry.get().strip()) if hasattr(self, 'port_entry') else getattr(self, 'port', 1235)
                    except Exception:
                        port = getattr(self, 'port', 1235)
                    self.server_status.config(text=f"🟡 Server: Unknown ({mode.upper()}:{port})")

        except Exception as e:
            logger.error(f"Error updating server status: {e}")

    def _apply_json_highlighting(self):
        """Apply basic JSON syntax highlighting to the route text"""
        try:
            content = self.route_text.get(1.0, tk.END)
            lines = content.split('\n')

            # Find the start of JSON content (after "Request Body:")
            json_start_line = 0
            for i, line in enumerate(lines):
                if "Request Body:" in line:
                    json_start_line = i + 1
                    break

            # Apply highlighting to JSON lines
            for i in range(json_start_line, len(lines)):
                line = lines[i]
                line_start = f"{i+1}.0"

                # Highlight JSON keys (text in quotes followed by colon)
                import re
                for match in re.finditer(r'"([^"]+)":', line):
                    start_col = match.start()
                    end_col = match.end() - 1  # Don't include the colon
                    start_pos = f"{i+1}.{start_col}"
                    end_pos = f"{i+1}.{end_col}"
                    self.route_text.tag_add("json_key", start_pos, end_pos)

                # Highlight string values
                for match in re.finditer(r':\s*"([^"]*)"', line):
                    start_col = match.start() + len(match.group().split('"')[0])
                    end_col = match.end()
                    start_pos = f"{i+1}.{start_col}"
                    end_pos = f"{i+1}.{end_col}"
                    self.route_text.tag_add("json_string", start_pos, end_pos)

                # Highlight numbers
                for match in re.finditer(r':\s*(\d+\.?\d*)', line):
                    start_col = match.start() + len(match.group().split(match.group(1))[0])
                    end_col = match.end()
                    start_pos = f"{i+1}.{start_col}"
                    end_pos = f"{i+1}.{end_col}"
                    self.route_text.tag_add("json_number", start_pos, end_pos)

        except Exception as e:
            # If highlighting fails, just continue without it
            pass
    


    
    def _get_local_ip(self):
        """Get the local IP address of the machine"""
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception as e:
            logger.error(f"Error getting local IP: {e}")
            # Use saved IP address as fallback instead of hardcoded 127.0.0.1
            return getattr(self, 'ip_address', '127.0.0.1')
    
    def _get_icon_path(self):
        """Get the path to the icon file for both development and compiled environments"""
        try:
            import os
            import sys
            
            # Handle both development and compiled environments
            if getattr(sys, 'frozen', False):
                # Running as compiled exe (Nuitka/PyInstaller)
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller
                    base_path = sys._MEIPASS
                else:
                    # Nuitka
                    base_path = os.path.dirname(sys.executable)
                
                # Try multiple possible locations for the icon
                possible_paths = [
                    os.path.join(base_path, 'qwen.ico'),
                    os.path.join(os.path.dirname(base_path), 'qwen.ico'),
                    os.path.join(base_path, 'main.dist', 'qwen.ico'),
                    os.path.join(base_path, 'main.onefile-build', 'qwen.ico')
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        return path
                
                # If not found in any of the expected locations, return the first one
                return possible_paths[0]
            else:
                # Running in development
                return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'qwen.ico')
                
        except Exception as e:
            logger.error(f"Error determining icon path: {e}")
            return None
    
    def _check_port_availability(self, ip_address, port):
        """Check if the port is available for binding"""
        try:
            import socket
            
            # First, check if port is already in use by trying to connect to it
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(1)
                result = test_sock.connect_ex((ip_address, port))
                test_sock.close()
                
                if result == 0:
                    return False, f"Port {port} is already in use by another application"
            except Exception:
                pass  # Continue with bind test even if connect test fails
            
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            
            # Try to bind to the port
            result = sock.bind((ip_address, port))
            sock.close()
            return True, None
        except socket.error as e:
            error_code = e.errno
            # Cross-platform error code mapping
            if error_code in [10048, 98]:  # WSAEADDRINUSE on Windows, EADDRINUSE on Linux/Mac
                return False, f"Port {port} is already in use by another application"
            elif error_code in [10013, 13]:  # WSAEACCES on Windows, EACCES on Linux/Mac
                return False, f"Port {port} requires elevated permissions (try running as administrator)"
            elif error_code in [10049, 99]:  # WSAEADDRNOTAVAIL on Windows, EADDRNOTAVAIL on Linux/Mac
                return False, f"IP address {ip_address} is not available on this machine"
            else:
                return False, f"Port {port} is not available: {str(e)}"
        except Exception as e:
            return False, f"Error checking port availability: {str(e)}"
    
    def _start_server(self):
        """Start the server"""
        if self.server_running:
            return
            
        # Get configuration from UI
        self.ip_address = self.ip_entry.get().strip()
        # Validate IP not empty
        if not self.ip_address:
            messagebox.showerror("Missing IP", "Please enter a valid IP address in Settings")
            return
        try:
            self.port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Port", "Please enter a valid port number")
            return
            
        self.mode = self.mode_var.get()

        # Validate cookie present before starting server
        try:
            cookie_text_current = self.cookie_text.get(1.0, tk.END).strip() if hasattr(self, 'cookie_text') else self.cookie_value
            self.cookie_value = cookie_text_current or self.cookie_value or ""
        except Exception:
            pass

        if not self.cookie_value:
            messagebox.showerror("Missing Cookie", "Please paste your Qwen cookie (JSON array) in Settings before starting the server")
            return
        
        # Check port availability before starting server
        if hasattr(self, 'connection_status'):
            self.connection_status.config(text="Checking port availability...")
            self.root.update()
        
        port_available, error_message = self._check_port_availability(self.ip_address, self.port)
        if not port_available:
            # Add helpful suggestions for common port conflicts
            suggestion = ""
            if self.port == 1235 and "already in use" in error_message:
                suggestion = "\n\n💡 Suggestion: Port 1235 might be used by LM Studio. Try stopping LM Studio or use a different port."
            elif self.port == 11434 and "already in use" in error_message:
                suggestion = "\n\n💡 Suggestion: Port 11434 might be used by Ollama. Try stopping Ollama or use a different port."
            elif "requires elevated permissions" in error_message:
                suggestion = "\n\n💡 Suggestion: Try running the application as administrator or use a port above 1024."
            
            messagebox.showerror("Port Not Available", error_message + suggestion)
            return
        
        # Start server in a separate thread
        self.connection_status.config(text="Starting server...")
        self.server_running = True
        self._update_status()
        
        # Start the actual Flask server
        def run_server():
            try:
                logger.info(f"Starting server on {self.ip_address}:{self.port} in {self.mode} mode")
                # Import server components here to avoid circular imports
                import main
                from main import app, chat_manager
                
                # Set server mode directly on server module to avoid desync
                try:
                    main.SERVER_MODE = self.mode
                except Exception:
                    pass
                
                # Initialize chat
                chat_id = chat_manager.initialize_chat()
                if chat_id:
                    self.update_chat_id(chat_id)
                    self.update_parent_id(None)
                
                # Run embedded Flask app (controllable stop)
                started = main.start_embedded(self.ip_address, self.port)
                if not started:
                    raise RuntimeError("Failed to start embedded server")
            except Exception as e:
                logger.error(f"Error starting server: {e}")
                self.server_running = False
                self._update_status()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Update status bar
        self._update_server_status()
        self.connection_status.config(text="Ready")
    
    def _stop_server(self):
        """Stop the server"""
        if not self.server_running:
            return
        
        # Show confirmation dialog
        result = messagebox.askyesno(
            "Stop Server",
            "Are you sure you want to stop the server?\n\n"
            f"Server: {self.ip_address}:{self.port}\n"
            f"Mode: {self.mode}\n\n"
            "Press 'Yes' to stop the server or 'No' to cancel.",
            icon='question'
        )
        
        if not result:
            return  # User clicked No
    
        self.connection_status.config(text="Stopping server...")
        self.server_running = False
        self._update_status()

        # Update status bar
        self._update_server_status()

        # Dừng Flask embedded mà không thoát app
        try:
            import main as _server
            _server.stop_embedded()
            self.connection_status.config(text="Stopped")
        except Exception as e:
            logger.warning(f"Embedded stop error: {e}")
    
    def _show_models(self):
        """Show available models with mode-specific formatting"""
        try:
            # Update status bar
            if hasattr(self, 'connection_status'):
                self.connection_status.config(text="Fetching models...")
                self.root.update()

            # Import here to avoid circular imports
            from services.qwen_service import qwen_service

            # Get current mode
            current_mode = getattr(self, 'mode_var', None)
            if current_mode:
                mode = current_mode.get()
            else:
                mode = self.mode or "lmstudio"  # Default to lmstudio

            # Get models from Qwen service
            models = qwen_service.get_models_from_qwen()

            # Update status bar
            if hasattr(self, 'connection_status'):
                self.connection_status.config(text=f"Found {len(models)} models")
                self.root.update()

            # Create a responsive popup window for models
            model_window = tk.Toplevel(self.root)
            model_window.title(f"Available Models - {mode.upper()} Mode")

            # Make popup responsive with scaling
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            scale = getattr(self, 'ui_scale', 1.1)

            base_popup_width = min(max(int(parent_width * 0.9), 800), 1300)
            base_popup_height = min(max(int(parent_height * 0.8), 500), 800)

            popup_width = int(base_popup_width * scale)
            popup_height = int(base_popup_height * scale)

            # Center popup relative to parent
            parent_x = self.root.winfo_x()
            parent_y = self.root.winfo_y()
            x = parent_x + (parent_width - popup_width) // 2
            y = parent_y + (parent_height - popup_height) // 2

            model_window.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
            model_window.resizable(True, True)
            model_window.minsize(700, 400)

            # Configure popup grid
            model_window.grid_rowconfigure(0, weight=1)
            model_window.grid_columnconfigure(0, weight=1)

            # Create main frame
            main_frame = ttk.Frame(model_window, style='Card.TFrame')
            main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            main_frame.grid_rowconfigure(2, weight=1)  # Content area gets most space
            main_frame.grid_columnconfigure(0, weight=1)

            # Create content based on mode
            if mode == "ollama":
                self._create_ollama_models_view(main_frame, models, popup_width)
            else:
                self._create_lmstudio_models_view(main_frame, models, popup_width)

            # Auto-resize popup width to evenly fit model cards
            try:
                model_window.update_idletasks()
                current_w = model_window.winfo_width()
                current_h = model_window.winfo_height()
                screen_w = self.root.winfo_screenwidth()
                screen_h = self.root.winfo_screenheight()

                # Decide columns similar to content (2 on wide, 1 on narrow)
                cols = 2 if current_w >= int(900 * scale) else 1
                # Estimate card width and paddings
                base_card_w = int(520 * scale)
                side_padding = int(40 * scale)  # margins + scrollbar
                target_w = base_card_w * cols + side_padding

                # Clamp to screen
                max_w = int(screen_w * 0.95)
                min_w = int(600 * scale)
                target_w = max(min_w, min(target_w, max_w))

                # Center the popup with new width
                parent_x = self.root.winfo_x()
                parent_y = self.root.winfo_y()
                parent_width = self.root.winfo_width()
                parent_height = self.root.winfo_height()
                x = parent_x + (parent_width - target_w) // 2
                y = parent_y + (parent_height - current_h) // 2
                model_window.geometry(f"{target_w}x{current_h}+{x}+{y}")
            except Exception:
                pass

            # Add close button
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=3, column=0, sticky="ew", pady=10)
            button_frame.grid_columnconfigure(0, weight=1)

            ttk.Button(button_frame,
                      text="Close",
                      style='Secondary.TButton',
                      command=model_window.destroy).grid(row=0, column=1, sticky="e")

        except Exception as e:
            # Reset status bar on error
            if hasattr(self, 'connection_status'):
                self.connection_status.config(text="Error fetching models")

            logger.error(f"Error showing models: {e}")
            messagebox.showerror("Error", f"Failed to show models: {str(e)}")

        finally:
            # Reset status bar after a delay
            if hasattr(self, 'connection_status'):
                self.root.after(3000, lambda: self.connection_status.config(text="Ready"))

    def _create_ollama_models_view(self, parent, models, popup_width):
        """Create Ollama-specific models view with copy buttons"""
        # Create scrollable frame for models (responsive, equalized cards)
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Grid the canvas and scrollbar
        canvas.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        scrollbar.grid(row=2, column=1, sticky="ns", pady=10)

        # Configure scrollable frame
        scrollable_frame.grid_columnconfigure(0, weight=1)

        # Grid config for equalized two-column layout on wide, one-column on narrow
        grid_cols = 2
        try:
            parent_width = parent.winfo_width() or popup_width
            if parent_width < 900:
                grid_cols = 1
        except Exception:
            grid_cols = 2

        for i, model in enumerate(models):
            model_id = model.get('id', 'Unknown')

            # Format model name for Ollama (add :latest if not present)
            if ':' not in model_id:
                ollama_name = f"{model_id}:latest"
            else:
                ollama_name = model_id

            # Create model card (equalized width)
            row = i // grid_cols
            col = i % grid_cols
            model_card = ttk.Frame(scrollable_frame, style='Card.TFrame', relief='raised', borderwidth=1)
            model_card.grid(row=row, column=col, sticky="nsew", padx=8, pady=6)
            scrollable_frame.grid_columnconfigure(col, weight=1)
            model_card.grid_columnconfigure(0, weight=1)

            # Model info
            info = model.get('info', {})
            meta = info.get('meta', {})
            context_window = meta.get('max_context_length', 'Unknown')

            # Format capabilities
            capabilities = info.get('capabilities', {})
            cap_list = []
            if capabilities.get('vision', False):
                cap_list.append('👁️ Vision')
            if capabilities.get('thinking', False):
                cap_list.append('🧠 Thinking')
            if capabilities.get('document', False):
                cap_list.append('📄 Document')

            # Model name (clickable for copy)
            name_frame = ttk.Frame(model_card)
            name_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=8)

            # Scale font size
            scale = getattr(self, 'ui_scale', 1.1)
            font_size = int(11 * scale)

            name_label = ttk.Label(name_frame,
                     text=ollama_name,
                     font=('Consolas', font_size, 'bold'),
                     foreground=self.colors['primary'])
            name_label.grid(row=0, column=0, sticky="w")

            # Copy button (no popup; change text to Copied then revert)
            copy_btn_width = int(8 * scale)
            copy_btn = ttk.Button(name_frame,
                                text="📋 Copy",
                                style='Secondary.TButton',
                                width=copy_btn_width,
                                command=lambda n=ollama_name, b_id=f"ollama_copy_{i}": self._copy_model_name(n, b_id))
            copy_btn.grid(row=0, column=1, sticky="e", padx=int(10 * scale))
            setattr(self, f"ollama_copy_{i}", copy_btn)

            # Model details
            details_frame = ttk.Frame(model_card)
            details_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=6)
            details_frame.grid_columnconfigure(1, weight=1)

            detail_font_size = int(9 * scale)

            # Extract context and generation length from model info.meta if available
            gen_len = meta.get('max_generation_length')
            if gen_len is None:
                gen_len = meta.get('max_thinking_generation_length')
            if gen_len is None:
                gen_len = meta.get('max_summary_generation_length')
            gen_len_text = str(gen_len) if gen_len is not None else 'Unknown'

            ttk.Label(details_frame, text="🧾 Context:", font=('Helvetica', detail_font_size, 'bold')).grid(row=0, column=0, sticky="w")
            ttk.Label(details_frame, text=str(context_window), font=('Helvetica', detail_font_size)).grid(row=0, column=1, sticky="w", padx=10)

            ttk.Label(details_frame, text="🧩 Generation:", font=('Helvetica', detail_font_size, 'bold')).grid(row=1, column=0, sticky="w")
            ttk.Label(details_frame, text=gen_len_text, font=('Helvetica', detail_font_size)).grid(row=1, column=1, sticky="w", padx=10)

            # Capabilities (from meta.capabilities)
            caps = meta.get('capabilities', {}) if isinstance(meta, dict) else {}
            cap_icons = []
            try:
                if caps.get('vision'): cap_icons.append('👁️ vision')
                if caps.get('document'): cap_icons.append('📄 document')
                if caps.get('video'): cap_icons.append('🎥 video')
                if caps.get('audio'): cap_icons.append('🎧 audio')
                if caps.get('citations'): cap_icons.append('📚 citations')
                if caps.get('thinking_budget'): cap_icons.append('🪙 budget')
                if caps.get('thinking'): cap_icons.append('🧠 thinking')
            except Exception:
                pass
            caps_text = ' • '.join(cap_icons) if cap_icons else 'None'
            ttk.Label(details_frame, text="🧰 Capabilities:", font=('Helvetica', detail_font_size, 'bold')).grid(row=2, column=0, sticky="w")
            ttk.Label(details_frame, text=caps_text, font=('Helvetica', detail_font_size)).grid(row=2, column=1, sticky="w", padx=10)

            # Thinking support and length (from abilities.thinking and max_thinking_generation_length)
            abilities = meta.get('abilities', {}) if isinstance(meta, dict) else {}
            has_thinking = abilities.get('thinking', 0) == 1 or caps.get('thinking', False) or caps.get('thinking_budget', False)
            thinking_len = meta.get('max_thinking_generation_length')
            thinking_text = ("Yes, " + str(thinking_len)) if (has_thinking and thinking_len is not None) else ('No' if not has_thinking else 'Yes, Unknown')
            ttk.Label(details_frame, text="🧠 Thinking:", font=('Helvetica', detail_font_size, 'bold')).grid(row=3, column=0, sticky="w")
            ttk.Label(details_frame, text=thinking_text, font=('Helvetica', detail_font_size)).grid(row=3, column=1, sticky="w", padx=10)

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            try:
                # Check if canvas still exists before scrolling
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                # Canvas might have been destroyed, ignore the event
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _create_lmstudio_models_view(self, parent, models, popup_width):
        """Create LM Studio-specific models view with copy buttons"""
        # Create scrollable frame for models (responsive, equalized cards)
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Grid the canvas and scrollbar
        canvas.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        scrollbar.grid(row=2, column=1, sticky="ns", pady=10)

        # Configure scrollable frame
        scrollable_frame.grid_columnconfigure(0, weight=1)

        # Grid config for equalized two-column layout on wide, one-column on narrow
        grid_cols = 2
        try:
            parent_width = parent.winfo_width() or popup_width
            if parent_width < 900:
                grid_cols = 1
        except Exception:
            grid_cols = 2

        # Add models with copy buttons (similar to Ollama but different styling)
        for i, model in enumerate(models):
            model_id = model.get('id', 'Unknown')

            # Create model card
            row = i // grid_cols
            col = i % grid_cols
            model_card = ttk.Frame(scrollable_frame, style='Card.TFrame', relief='raised', borderwidth=1)
            model_card.grid(row=row, column=col, sticky="nsew", padx=8, pady=6)
            scrollable_frame.grid_columnconfigure(col, weight=1)
            model_card.grid_columnconfigure(0, weight=1)

            # Model info
            info = model.get('info', {})
            meta = info.get('meta', {})
            context_window = meta.get('max_context_length', 'Unknown')

            # Format capabilities
            capabilities = info.get('capabilities', {})
            cap_list = []
            if capabilities.get('vision', False):
                cap_list.append('👁️ Vision')
            if capabilities.get('thinking', False):
                cap_list.append('🧠 Thinking')
            if capabilities.get('document', False):
                cap_list.append('📄 Document')
            capabilities_str = ' • '.join(cap_list) if cap_list else '⚡ Basic'

            # Model name (clickable for copy)
            name_frame = ttk.Frame(model_card)
            name_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=8)

            # Scale font size
            scale = getattr(self, 'ui_scale', 1.5)
            font_size = int(11 * scale)

            name_lbl = ttk.Label(name_frame,
                     text=model_id,
                     font=('Consolas', font_size, 'bold'),
                     foreground=self.colors['primary'])
            name_lbl.grid(row=0, column=0, sticky="w")

            # Copy button with unique ID for state management
            copy_btn_id = f"copy_btn_{i}"
            copy_btn_width = int(8 * scale)  # Scale button width
            copy_btn = ttk.Button(name_frame,
                                text="📋 Copy",
                                style='Secondary.TButton',
                                width=copy_btn_width,
                                command=lambda name=model_id, btn_id=copy_btn_id: self._copy_model_name(name, btn_id))
            copy_btn.grid(row=0, column=1, sticky="e", padx=int(10 * scale))

            # Store button reference for later state changes
            setattr(self, copy_btn_id, copy_btn)

            # Add tooltip functionality
            self._create_tooltip(copy_btn, f"Copy '{model_id}' to clipboard")

            # Model details
            details_frame = ttk.Frame(model_card)
            details_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=6)
            details_frame.grid_columnconfigure(1, weight=1)

            detail_font_size = int(9 * scale)

            # Extract gen length like above
            gen_len = meta.get('max_generation_length')
            if gen_len is None:
                gen_len = meta.get('max_thinking_generation_length')
            if gen_len is None:
                gen_len = meta.get('max_summary_generation_length')
            gen_len_text = str(gen_len) if gen_len is not None else 'Unknown'

            ttk.Label(details_frame, text="🧾 Context:", font=('Helvetica', detail_font_size, 'bold')).grid(row=0, column=0, sticky="w")
            ttk.Label(details_frame, text=str(context_window), font=('Helvetica', detail_font_size)).grid(row=0, column=1, sticky="w", padx=10)

            ttk.Label(details_frame, text="🧩 Generation:", font=('Helvetica', detail_font_size, 'bold')).grid(row=1, column=0, sticky="w")
            ttk.Label(details_frame, text=gen_len_text, font=('Helvetica', detail_font_size)).grid(row=1, column=1, sticky="w", padx=10)

            # Capabilities (from meta.capabilities)
            caps = meta.get('capabilities', {}) if isinstance(meta, dict) else {}
            cap_icons = []
            try:
                if caps.get('vision'): cap_icons.append('👁️ vision')
                if caps.get('document'): cap_icons.append('📄 document')
                if caps.get('video'): cap_icons.append('🎥 video')
                if caps.get('audio'): cap_icons.append('🎧 audio')
                if caps.get('citations'): cap_icons.append('📚 citations')
                if caps.get('thinking_budget'): cap_icons.append('🪙 budget')
                if caps.get('thinking'): cap_icons.append('🧠 thinking')
            except Exception:
                pass
            caps_text = ' • '.join(cap_icons) if cap_icons else 'None'
            ttk.Label(details_frame, text="🧰 Capabilities:", font=('Helvetica', detail_font_size, 'bold')).grid(row=2, column=0, sticky="w")
            ttk.Label(details_frame, text=caps_text, font=('Helvetica', detail_font_size)).grid(row=2, column=1, sticky="w", padx=10)

            # Thinking support and length
            abilities = meta.get('abilities', {}) if isinstance(meta, dict) else {}
            has_thinking = abilities.get('thinking', 0) == 1 or caps.get('thinking', False) or caps.get('thinking_budget', False)
            thinking_len = meta.get('max_thinking_generation_length')
            thinking_text = ("Yes, " + str(thinking_len)) if (has_thinking and thinking_len is not None) else ('No' if not has_thinking else 'Yes, Unknown')
            ttk.Label(details_frame, text="🧠 Thinking:", font=('Helvetica', detail_font_size, 'bold')).grid(row=3, column=0, sticky="w")
            ttk.Label(details_frame, text=thinking_text, font=('Helvetica', detail_font_size)).grid(row=3, column=1, sticky="w", padx=10)

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            try:
                # Check if canvas still exists before scrolling
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                # Canvas might have been destroyed, ignore the event
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard and show confirmation (for Ollama)"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()  # Ensure clipboard is updated

            # Persist selected model
            self.selected_model = text
            self._save_settings()

            # Show temporary confirmation
            self._show_copy_confirmation(text)

        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            messagebox.showerror("Error", f"Failed to copy to clipboard: {str(e)}")

    def _copy_model_name(self, model_name, button_id):
        """Copy model name to clipboard and update button state (for LM Studio)"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(model_name)
            self.root.update()  # Ensure clipboard is updated

            # Persist selected model
            self.selected_model = model_name
            self._save_settings()

            # Get the button reference
            if hasattr(self, button_id):
                button = getattr(self, button_id)

                # Change button text to "Copied"
                button.config(text="✅ Copied")

                # Reset button text after 3 seconds
                self.root.after(3000, lambda: self._reset_copy_button(button))

        except Exception as e:
            logger.error(f"Error copying model name to clipboard: {e}")

    def _reset_copy_button(self, button):
        """Reset copy button text back to 'Copy'"""
        try:
            if button.winfo_exists():  # Check if button still exists
                button.config(text="📋 Copy")
        except Exception as e:
            # Button might have been destroyed, ignore
            pass

    def _show_copy_confirmation(self, text):
        """Show a temporary confirmation that text was copied"""
        # Create a temporary popup with scaling
        scale = getattr(self, 'ui_scale', 1.1)
        popup_width = int(300 * scale)
        popup_height = int(80 * scale)

        confirm_popup = tk.Toplevel(self.root)
        confirm_popup.title("Copied!")
        confirm_popup.geometry(f"{popup_width}x{popup_height}")
        confirm_popup.resizable(False, False)

        # Center the popup
        confirm_popup.transient(self.root)
        confirm_popup.grab_set()

        # Position relative to mouse or center of parent with scaling
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - popup_width // 2
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - popup_height // 2
        confirm_popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        # Content with scaled fonts
        title_font_size = int(10 * scale)
        text_font_size = int(9 * scale)

        ttk.Label(confirm_popup,
                 text="✅ Copied to clipboard:",
                 font=('Helvetica', title_font_size, 'bold')).pack(pady=5)

        ttk.Label(confirm_popup,
                 text=text,
                 font=('Consolas', text_font_size),
                 foreground=self.colors['primary']).pack(pady=5)

        # Auto-close after 2 seconds
        confirm_popup.after(2000, confirm_popup.destroy)

        # Allow manual close with Escape or click
        confirm_popup.bind('<Escape>', lambda e: confirm_popup.destroy())
        confirm_popup.bind('<Button-1>', lambda e: confirm_popup.destroy())

    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            # Scale tooltip font
            scale = getattr(self, 'ui_scale', 1.1)
            tooltip_font_size = int(8 * scale)

            label = ttk.Label(tooltip, text=text,
                            background="lightyellow",
                            relief="solid",
                            borderwidth=1,
                            font=('Helvetica', tooltip_font_size))
            label.pack()

            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _show_routes(self):
        """Show available API routes for current mode"""
        # Create a responsive popup window
        routes_window = tk.Toplevel(self.root)
        routes_window.title(f"API Routes - {self.mode or 'No Mode'} Mode")

        # Make popup responsive with scaling
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()
        scale = getattr(self, 'ui_scale', 1.1)

        base_popup_width = min(max(int(parent_width * 0.8), 600), 1000)
        base_popup_height = min(max(int(parent_height * 0.8), 500), 800)

        popup_width = int(base_popup_width * scale)
        popup_height = int(base_popup_height * scale)

        # Center popup relative to parent
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        x = parent_x + (parent_width - popup_width) // 2
        y = parent_y + (parent_height - popup_height) // 2

        routes_window.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        routes_window.resizable(True, True)
        routes_window.minsize(500, 400)

        # Configure popup grid
        routes_window.grid_rowconfigure(0, weight=1)
        routes_window.grid_columnconfigure(0, weight=1)

        # Main frame with responsive grid
        main_frame = ttk.Frame(routes_window)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ttk.Label(main_frame,
                               text=f"Available API Routes - {self.mode or 'No Mode'} Mode",
                               font=('Helvetica', int(14 * scale), 'bold'))
        title_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        # Create scrolled text widget for routes
        routes_text = scrolledtext.ScrolledText(main_frame,
                                              wrap=tk.WORD,
                                              font=('Consolas', int(10 * scale)),
                                              state=tk.NORMAL)
        routes_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        # Generate routes content based on mode
        routes_content = self._get_routes_content()
        routes_text.insert(tk.END, routes_content)
        routes_text.config(state=tk.DISABLED)

        # Close button
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew", pady=5)
        button_frame.grid_columnconfigure(0, weight=1)

        ttk.Button(button_frame,
                  text="Close",
                  command=routes_window.destroy).grid(row=0, column=1, sticky="e")

    def _get_routes_content(self):
        """Get the routes content based on current mode"""
        current_mode = getattr(self, 'mode_var', None)
        if current_mode:
            mode = current_mode.get()
        else:
            mode = self.mode

        if mode == "lmstudio":
            return """🚀 LM Studio Compatible API Routes

📋 Available Endpoints:
┌─────────────────────────────────────────────────────────────────┐
│ Method │ Endpoint                    │ Description                │
├─────────────────────────────────────────────────────────────────┤
│ GET    │ /                          │ Root endpoint              │
│ GET    │ /v1/models                 │ List available models      │
│ GET    │ /v1/models/{model_id}      │ Get specific model info    │
│ POST   │ /v1/chat/completions       │ Chat completions           │
│ POST   │ /v1/completions            │ Text completions (deprecated) │
│ POST   │ /v1/embeddings             │ Text embeddings (not supported) │
└─────────────────────────────────────────────────────────────────┘

🔧 Features:
• OpenAI API compatible format
• Think mode with <think></think> tags
• Streaming and non-streaming responses
• Queue system for request management
• Compatible with LM Studio clients

📝 Example Usage:
curl -X POST http://localhost:1235/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "qwen3-235b-a22b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
"""
        elif mode == "ollama":
            return """🤖 Ollama Compatible API Routes

📋 Available Endpoints:
┌─────────────────────────────────────────────────────────────────┐
│ Method │ Endpoint                    │ Description                │
├─────────────────────────────────────────────────────────────────┤
│ GET    │ /                          │ Root endpoint              │
│ GET    │ /api/version               │ Get Ollama version         │
│ GET    │ /api/tags                  │ List available models      │
│ GET    │ /api/ps                    │ List running models        │
│ POST   │ /api/show                  │ Show model details         │
│ POST   │ /api/generate              │ Generate response          │
│ POST   │ /api/chat                  │ Chat endpoint              │
└─────────────────────────────────────────────────────────────────┘

🔧 Features:
• Ollama API compatible format
• Think mode with thinking field in response
• Image support (base64 images)
• Streaming and non-streaming responses
• Queue system for request management
• Compatible with Ollama clients

📝 Example Usage:
curl -X POST http://localhost:11434/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "qwen3-235b-a22b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
"""
        else:
            return """❌ No Mode Selected

Please select a server mode first:

🚀 LM Studio Mode:
• Port: 1235
• OpenAI API compatible
• Think mode with <think></think> tags
• Compatible with LM Studio clients

🤖 Ollama Mode:
• Port: 11434
• Ollama API compatible
• Think mode with thinking field
• Image support
• Compatible with Ollama clients

Use the Settings tab to configure the server mode.
"""

    def _create_new_chat(self):
        """Create a new chat session with confirmation"""
        try:
            # Show confirmation dialog first
            current_chat = self.current_chat_id or "None"
            result = messagebox.askyesno(
                "New Chat Session",
                f"Create a new chat session?\n\n"
                f"Current chat: {current_chat}\n"
                f"This will start a fresh conversation.",
                icon='question'
            )

            if not result:
                return  # User clicked No

            # Import here to avoid circular imports
            from utils.chat_manager import chat_manager

            # Create new chat
            chat_id = chat_manager.create_new_chat()
            if chat_id:
                self.update_chat_id(chat_id)
                self.update_parent_id(None)

                # Add to chat history
                self._add_to_chat_history(f"New chat session created: {chat_id}")

                # Update status bar briefly
                if hasattr(self, 'connection_status'):
                    self.connection_status.config(text=f"New chat: {chat_id[:8]}...")
                    self.root.after(3000, lambda: self.connection_status.config(text="Ready"))

                messagebox.showinfo("Success", f"New chat session created: {chat_id}")
            else:
                messagebox.showerror("Error", "Failed to create new chat session")

        except Exception as e:
            logger.error(f"Error creating new chat: {e}")
            messagebox.showerror("Error", f"Failed to create new chat: {str(e)}")
    
    def _show_logs(self):
        """Show logs in the logs tab"""
        self.notebook.select(1)  # Select the logs tab
    
    def _clear_logs(self):
        """Clear the log display"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_lines = []
    
    def _apply_configuration(self):
        """Apply the server configuration"""
        # Get values from UI
        ip = self.ip_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Port", "Please enter a valid port number")
            return

        mode = self.mode_var.get()

        # Get scale value
        try:
            scale_str = self.scale_var.get()
            scale_percent = int(scale_str.replace('%', ''))
            new_scale = scale_percent / 100.0
        except ValueError:
            messagebox.showerror("Invalid Scale", "Please select a valid scale percentage")
            return

        # Validate IP address
        if not ip:
            messagebox.showerror("Invalid IP", "Please enter a valid IP address")
            return

        # Update configuration
        self.ip_address = ip
        self.port = port
        self.mode = mode

        # Check if scale changed
        scale_changed = abs(self.ui_scale - new_scale) > 0.01
        self.ui_scale = new_scale

        # Read cookie text (if present in UI)
        try:
            if hasattr(self, 'cookie_text'):
                self.cookie_value = self.cookie_text.get(1.0, tk.END).strip()
        except Exception:
            pass
        # Read optional bx headers (if present in UI)
        try:
            if hasattr(self, 'bx_ua_entry'):
                self.bx_ua_value = (self.bx_ua_entry.get() or "").strip()
            if hasattr(self, 'bx_umidtoken_entry'):
                self.bx_umidtoken_value = (self.bx_umidtoken_entry.get() or "").strip()
        except Exception:
            pass

        # Save updated settings
        self._save_settings()

        if scale_changed:
            messagebox.showinfo("Configuration",
                              f"Configuration applied successfully.\n\n"
                              f"UI scale changed to {scale_percent}%.\n"
                              "Please restart the application for the new scale to take full effect.")
        else:
            messagebox.showinfo("Configuration", "Configuration applied successfully")

        # Update routes display after configuration change
        self._update_routes_display()

    def _auto_set_port(self):
        """Automatically set the port based on selected mode"""
        mode = self.mode_var.get()
        if mode == "lmstudio":
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, "1235")
        elif mode == "ollama":
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, "11434")

    def _on_mode_changed(self, event=None):
        """Handle mode selection change"""
        self.mode_description.config(text=self._get_mode_description())
        self._update_routes_display()
        # Optionally auto-set port when mode changes
        # self._auto_set_port()

    def _on_scale_changed(self, event=None):
        """Handle UI scale change"""
        try:
            scale_str = self.scale_var.get()
            scale_percent = int(scale_str.replace('%', ''))
            new_scale = scale_percent / 100.0

            # Update scale immediately for live preview
            old_scale = self.ui_scale
            self._last_scale = old_scale  # Store for font calculations
            self.ui_scale = new_scale

            # Update scale description immediately
            self.scale_description.config(text=f"Current: {scale_percent}% - Adjusts all UI elements size")

            # Apply new scale immediately
            self._apply_scale_immediately(new_scale)

            # Update status bar to show new scale and refresh server status
            self._trigger_window_resize_update()
            self._update_server_status()

            # Save updated settings
            self._save_settings()

        except Exception as e:
            logger.error(f"Error changing scale: {e}")
            messagebox.showerror("Error", f"Failed to change scale: {str(e)}")

    def _apply_scale_immediately(self, new_scale):
        """Apply new scale immediately without restart"""
        try:
            # Update the scale
            self.ui_scale = new_scale

            # Reapply default fonts with new scale
            self._setup_default_fonts()

            # Reapply styles with new scale
            self._setup_styles()

            # Update specific widget fonts
            self._update_widget_fonts()

            # Update window size if needed
            self._update_window_size_for_scale()

            # Force a complete UI refresh
            self.root.update_idletasks()
            self.root.update()

            logger.info(f"UI scale applied immediately: {int(new_scale * 100)}%")

        except Exception as e:
            logger.error(f"Error applying scale immediately: {e}")

    def _refresh_model_cache(self):
        """Refresh model cache by calling qwen_service directly"""
        try:
            # Show loading message
            if hasattr(self, 'connection_status'):
                self.connection_status.config(text="Refreshing model cache...")
                self.root.update()
            
            # Import and call qwen_service directly
            from services.qwen_service import qwen_service
            
            # Force refresh by calling get_models_from_qwen with force refresh
            # We need to access the global cache in main.py
            import sys
            import os
            
            # Get the server module to access the global cache
            server_module = sys.modules.get('server')
            if server_module and hasattr(server_module, 'get_cached_qwen_models'):
                # Call the cached function with force refresh
                models = server_module.get_cached_qwen_models(force_refresh=True)
                count = len(models) if models else 0
                
                # Show success message
                messagebox.showinfo("Success", 
                    f"Model cache refreshed successfully!\n\n"
                    f"• Models found: {count}")
                
                # Update status
                if hasattr(self, 'connection_status'):
                    self.connection_status.config(text=f"Model cache refreshed ({count} models)")
                    # Reset status after 3 seconds
                    self.root.after(3000, lambda: self.connection_status.config(text="Ready"))
            else:
                # Fallback: call qwen_service directly
                models = qwen_service.get_models_from_qwen()
                count = len(models) if models else 0
                
                # Show success message
                messagebox.showinfo("Success", 
                    f"Model cache refreshed successfully!\n\n"
                    f"• Models found: {count}")
                
                # Update status
                if hasattr(self, 'connection_status'):
                    self.connection_status.config(text=f"Model cache refreshed ({count} models)")
                    # Reset status after 3 seconds
                    self.root.after(3000, lambda: self.connection_status.config(text="Ready"))
                    
        except Exception as e:
            logger.error(f"Error refreshing model cache: {e}")
            messagebox.showerror("Error", f"Failed to refresh model cache: {str(e)}")
            if hasattr(self, 'connection_status'):
                self.connection_status.config(text="Refresh failed")
                self.root.after(3000, lambda: self.connection_status.config(text="Ready"))

    def _trigger_window_resize_update(self):
        """Trigger a window resize update to refresh status bar"""
        try:
            # Get current window size
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            # Manually trigger the resize handler to update status bar
            if hasattr(self, 'window_info'):
                try:
                    from config import VERSION
                    version_text = f"v{VERSION}"
                except ImportError:
                    version_text = "v1.0.1"
                    
                responsive_indicator = "📱" if width < 900 else "🖥️" if width > 1200 else "💻"
                scale_percent = int(self.ui_scale * 100)
                self.window_info.config(text=f"{version_text} • {responsive_indicator} {width}x{height} • {scale_percent}%")

        except Exception as e:
            logger.error(f"Error triggering window resize update: {e}")

    def _update_window_size_for_scale(self):
        """Update window size to accommodate new scale"""
        try:
            # Get current window size
            current_geometry = self.root.geometry()
            width, height, x, y = map(int, current_geometry.replace('x', '+').replace('+', ' ').split())

            # Calculate new size based on scale (but don't make it too big)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            # Ensure window doesn't exceed 90% of screen size
            max_width = int(screen_width * 0.9)
            max_height = int(screen_height * 0.9)

            # Keep current size but ensure it's reasonable for the scale
            new_width = min(width, max_width)
            new_height = min(height, max_height)

            # Center if window is getting larger
            new_x = max(0, (screen_width - new_width) // 2)
            new_y = max(0, (screen_height - new_height) // 2)

            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")

        except Exception as e:
            logger.error(f"Error updating window size for scale: {e}")

    def _update_widget_fonts(self):
        """Update fonts for all widgets when scale changes"""
        try:
            scale = self.ui_scale

            # Update text widgets
            if hasattr(self, 'route_text'):
                route_font_size = int(10 * scale)
                self.route_text.config(font=('Consolas', route_font_size))

            if hasattr(self, 'log_text'):
                log_font_size = int(10 * scale)
                self.log_text.config(font=('Consolas', log_font_size))

            if hasattr(self, 'chat_history_text'):
                chat_font_size = int(10 * scale)
                self.chat_history_text.config(font=('Helvetica', chat_font_size))

            if hasattr(self, 'routes_text'):
                routes_font_size = int(10 * scale)
                self.routes_text.config(font=('Consolas', max(routes_font_size - 1, 8)))

            if hasattr(self, 'cookie_text'):
                cookie_font_size = int(9 * scale)
                self.cookie_text.config(font=('Consolas', cookie_font_size))

            entry_font_size = int(9 * scale)
            if hasattr(self, 'bx_ua_entry'):
                self.bx_ua_entry.config(font=('Consolas', entry_font_size))
            if hasattr(self, 'bx_umidtoken_entry'):
                self.bx_umidtoken_entry.config(font=('Consolas', entry_font_size))

            # Update status labels
            status_font_size = int(10 * scale)
            if hasattr(self, 'server_status_value'):
                self.server_status_value.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'server_mode_value'):
                self.server_mode_value.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'server_port_value'):
                self.server_port_value.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'server_host_value'):
                self.server_host_value.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'queue_status'):
                self.queue_status.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'queue_size_label'):
                self.queue_size_label.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'chat_id_value'):
                self.chat_id_value.config(font=('Helvetica', status_font_size))
            if hasattr(self, 'parent_id_value'):
                self.parent_id_value.config(font=('Helvetica', status_font_size))

            # Update status bar labels
            status_bar_font_size = int(9 * scale)
            if hasattr(self, 'connection_status'):
                self.connection_status.config(font=('Helvetica', status_bar_font_size))
            if hasattr(self, 'server_status'):
                self.server_status.config(font=('Helvetica', status_bar_font_size))
            if hasattr(self, 'window_info'):
                self.window_info.config(font=('Helvetica', status_bar_font_size))

            # Update entry widgets
            entry_font_size = int(10 * scale)
            if hasattr(self, 'ip_entry'):
                self.ip_entry.config(font=('Helvetica', entry_font_size))
            if hasattr(self, 'port_entry'):
                self.port_entry.config(font=('Helvetica', entry_font_size))

            # Update combobox widgets (need to recreate style)
            if hasattr(self, 'mode_var'):
                # Force combobox to refresh by temporarily changing value
                current_mode = self.mode_var.get()
                self.mode_var.set("")
                self.root.update_idletasks()
                self.mode_var.set(current_mode)

            if hasattr(self, 'scale_var'):
                current_scale = self.scale_var.get()
                self.scale_var.set("")
                self.root.update_idletasks()
                self.scale_var.set(current_scale)

            # Update description labels
            desc_font_size = int(9 * scale)
            if hasattr(self, 'scale_description'):
                self.scale_description.config(font=('Helvetica', desc_font_size))
            if hasattr(self, 'mode_description'):
                self.mode_description.config(font=('Helvetica', desc_font_size))

            # Update route text tags
            if hasattr(self, 'route_text'):
                self.route_text.tag_configure("route_header", 
                    foreground="#2980b9", 
                    font=('Consolas', int(10 * scale), 'bold'))
                self.route_text.tag_configure("body_header", 
                    foreground="#27ae60", 
                    font=('Consolas', int(10 * scale), 'bold'))

            logger.info(f"Updated fonts for all widgets with scale {int(scale * 100)}%")

        except Exception as e:
            logger.error(f"Error updating widget fonts: {e}")
            status_font_size = int(9 * scale)
            self.window_info.config(font=('Helvetica', status_font_size))

            # Update button widths (approximate scaling)
            self._update_button_sizes()
            
            # Update all ttk labels recursively
            self._update_ttk_labels_recursive(self.root, scale)

        except Exception as e:
            logger.error(f"Error updating widget fonts: {e}")

    def _show_about(self):
        """Show about dialog with version and application info"""
        try:
            # Get version
            try:
                from config import VERSION
                version_text = VERSION
            except ImportError:
                version_text = "1.0.1"
            
            about_text = f"""🎯 QwenToApi v{version_text}

📋 Description:
QwenToApi là server tùy chỉnh tích hợp với Qwen API, 
hỗ trợ cả LM Studio và Ollama format.

🚀 Features:
• Dual Mode: LM Studio (port 1235) và Ollama (port 11434)
• Think Mode: Hỗ trợ tính năng suy nghĩ của Qwen
• Image Support: Xử lý hình ảnh base64 (Ollama mode)
• Queue System: Hệ thống xếp hàng xử lý request
• Background Mode: Chạy server trong background

👨‍💻 Developer: KhanhNguyen9872
🌐 License: MIT License

📞 Support:
GitHub: https://github.com/khanhnguyen9872/custom_server_lmstudio

🔄 Keyboard Shortcuts:
Ctrl+S    - Start Server
Ctrl+Q    - Stop Server
Ctrl+N    - New Chat
Ctrl+M    - Show Models
Ctrl+R    - Show Routes
F1        - Show Help
F5        - Refresh Status
Escape    - Close Popups"""
            
            self._show_help_window(about_text)
            
        except Exception as e:
            logger.error(f"Error showing about dialog: {e}")
            messagebox.showerror("Error", f"Failed to show about dialog: {str(e)}")

    def _show_help_window(self, help_text):
        """Show help window with keyboard shortcuts"""
        try:
            # Create a responsive popup window for help
            help_window = tk.Toplevel(self.root)
            help_window.title("Help - Keyboard Shortcuts")

            # Make popup responsive with scaling
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            scale = getattr(self, 'ui_scale', 1.1)

            base_popup_width = min(max(int(parent_width * 0.7), 600), 1000)
            base_popup_height = min(max(int(parent_height * 0.6), 400), 700)

            popup_width = int(base_popup_width * scale)
            popup_height = int(base_popup_height * scale)

            # Center popup relative to parent
            parent_x = self.root.winfo_x()
            parent_y = self.root.winfo_y()
            x = parent_x + (parent_width - popup_width) // 2
            y = parent_y + (parent_height - popup_height) // 2

            help_window.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
            help_window.resizable(True, True)
            help_window.minsize(500, 300)

            # Configure popup grid
            help_window.grid_rowconfigure(0, weight=1)
            help_window.grid_columnconfigure(0, weight=1)

            # Main frame
            main_frame = ttk.Frame(help_window)
            main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            main_frame.grid_rowconfigure(1, weight=1)
            main_frame.grid_columnconfigure(0, weight=1)

            # Title
            title_label = ttk.Label(main_frame,
                                   text="Help - Keyboard Shortcuts",
                                   font=('Helvetica', int(14 * scale), 'bold'))
            title_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))

            # Help text
            help_text_widget = scrolledtext.ScrolledText(main_frame,
                                                        wrap=tk.WORD,
                                                        font=('Consolas', int(10 * scale)),
                                                        state=tk.NORMAL)
            help_text_widget.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
            help_text_widget.insert(tk.END, help_text)
            help_text_widget.config(state=tk.DISABLED)

            # Close button
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=2, column=0, sticky="ew", pady=5)
            button_frame.grid_columnconfigure(0, weight=1)

            ttk.Button(button_frame,
                      text="Close",
                      command=help_window.destroy).grid(row=0, column=1, sticky="e")

        except Exception as e:
            logger.error(f"Error showing help window: {e}")
            # Fallback to messagebox if custom window fails
            messagebox.showinfo("Help - Keyboard Shortcuts", help_text)

    def _update_ttk_labels_recursive(self, widget, scale):
        """Recursively update all ttk labels with new font scale"""
        try:
            widget_class = widget.winfo_class()
            
            # Update ttk labels
            if widget_class == 'TLabel':
                try:
                    # Get current font configuration
                    current_font = widget.cget('font')
                    if current_font:
                        # Parse font tuple and update size
                        if isinstance(current_font, tuple) and len(current_font) >= 2:
                            family, size = current_font[0], current_font[1]
                            if isinstance(size, int):
                                # Calculate new size based on scale
                                new_size = int(size * scale / getattr(self, '_last_scale', 1.0))
                                new_font = (family, new_size) + current_font[2:]
                                widget.configure(font=new_font)
                except Exception:
                    pass  # Skip if font config fails
            
            # Recursively update children
            for child in widget.winfo_children():
                self._update_ttk_labels_recursive(child, scale)
                
        except Exception as e:
            # Continue with other widgets if one fails
            pass


    def _update_button_sizes(self):
        """Update button sizes based on current scale"""
        try:
            scale = self.ui_scale

            # Find and update buttons with specific widths
            for widget_name in dir(self):
                widget = getattr(self, widget_name)
                if hasattr(widget, 'winfo_class') and widget.winfo_class() == 'Button':
                    try:
                        # Get current width and scale it
                        current_width = widget.cget('width')
                        if current_width and isinstance(current_width, int):
                            new_width = max(int(current_width * scale), current_width)
                            widget.config(width=new_width)
                    except:
                        pass  # Skip if widget doesn't support width config

        except Exception as e:
            logger.error(f"Error updating button sizes: {e}")

    def _force_widget_update(self):
        """Force update all widgets to apply new scaling"""
        try:
            scale = self.ui_scale

            # Update the root window to trigger recalculation
            self.root.update_idletasks()

            # Update specific widgets that need manual scaling

            # Update notebook tab font size
            if hasattr(self, 'notebook'):
                tab_font_size = int(10 * scale)
                style = ttk.Style()
                style.configure('TNotebook.Tab', font=('Helvetica', tab_font_size))

            # Recursively update all widgets
            self._update_widget_recursive(self.root, scale)

            # Force a complete redraw
            self.root.update()

        except Exception as e:
            logger.error(f"Error forcing widget update: {e}")

    def _update_widget_recursive(self, widget, scale):
        """Recursively update all widgets with new scale"""
        try:
            widget_class = widget.winfo_class()

            # Update fonts for different widget types
            if widget_class in ['Button', 'TButton']:
                font_size = int(10 * scale)
                try:
                    widget.config(font=('Helvetica', font_size))
                except:
                    pass
            elif widget_class in ['Entry', 'TEntry']:
                font_size = int(10 * scale)
                try:
                    widget.config(font=('Helvetica', font_size))
                except:
                    pass
            elif widget_class in ['Combobox', 'TCombobox']:
                font_size = int(10 * scale)
                try:
                    widget.config(font=('Helvetica', font_size))
                except:
                    pass
            elif widget_class in ['Label', 'TLabel']:
                # Labels are handled by styles, but update custom ones
                try:
                    current_font = widget.cget('font')
                    if current_font and isinstance(current_font, tuple) and len(current_font) >= 2:
                        family, size = current_font[0], current_font[1]
                        if isinstance(size, int):
                            new_size = int(size * scale / getattr(self, '_last_scale', 1.0))
                            widget.config(font=(family, new_size) + current_font[2:])
                except:
                    pass

            # Recursively update children
            for child in widget.winfo_children():
                self._update_widget_recursive(child, scale)

        except Exception as e:
            # Continue with other widgets if one fails
            pass

    def _load_settings(self):
        """Load settings (ui_scale, ip, port, mode, selected_model) from file"""
        try:
            import json
            settings_file = "ui_settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.ui_scale = settings.get('ui_scale', self.ui_scale)
                    self.ip_address = settings.get('ip_address', self.ip_address)
                    self.port = settings.get('port', self.port)
                    self.mode = settings.get('mode', self.mode)
                    self.selected_model = settings.get('selected_model', self.selected_model)
                    self.cookie_value = settings.get('cookie', self.cookie_value)
                    self.bx_ua_value = settings.get('bx_ua', getattr(self, 'bx_ua_value', '') or '')
                    self.bx_umidtoken_value = settings.get('bx_umidtoken', getattr(self, 'bx_umidtoken_value', '') or '')
        except Exception as e:
            logger.warning(f"Could not load settings: {e}")

    def _save_settings(self):
        """Persist settings (ui_scale, ip, port, mode, selected_model) to file"""
        try:
            import json
            settings_file = "ui_settings.json"

            # Load existing settings or create new
            settings = {}
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                except Exception:
                    settings = {}

            # Update settings
            settings['ui_scale'] = self.ui_scale
            settings['ip_address'] = self.ip_address
            settings['port'] = self.port
            settings['mode'] = self.mode
            if getattr(self, 'selected_model', None):
                settings['selected_model'] = self.selected_model
            if getattr(self, 'cookie_value', None) is not None:
                settings['cookie'] = self.cookie_value
            if getattr(self, 'bx_ua_value', None) is not None:
                settings['bx_ua'] = self.bx_ua_value
            if getattr(self, 'bx_umidtoken_value', None) is not None:
                settings['bx_umidtoken'] = self.bx_umidtoken_value

            # Save settings
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Could not save settings: {e}")

    def _get_mode_description(self):
        """Get description for the current mode"""
        current_mode = getattr(self, 'mode_var', None)
        if current_mode:
            mode = current_mode.get()
        else:
            mode = self.mode

        return ""

    def _update_routes_display(self):
        """Update the routes display based on current mode"""
        if hasattr(self, 'routes_text'):
            self.routes_text.config(state=tk.NORMAL)
            self.routes_text.delete(1.0, tk.END)
            self.routes_text.insert(tk.END, self._get_routes_content())
            self.routes_text.config(state=tk.DISABLED)
    
    def _add_to_chat_history(self, message):
        """Add a message to the chat history"""
        self.chat_history.append(f"{datetime.now().strftime('%H:%M:%S')}: {message}")
        
        # Keep only the last N messages
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]
        
        # Update the display if chat history widget exists; otherwise fallback to logs
        try:
            if hasattr(self, 'chat_history_text') and self.chat_history_text:
                self.chat_history_text.config(state=tk.NORMAL)
                self.chat_history_text.delete(1.0, tk.END)
                for msg in self.chat_history:
                    self.chat_history_text.insert(tk.END, msg + "\n")
                self.chat_history_text.config(state=tk.DISABLED)
                self.chat_history_text.see(tk.END)
            else:
                # Fallback: write last message to logs area
                if self.chat_history:
                    self.log(self.chat_history[-1])
        except Exception:
            # Silently ignore UI update errors
            pass
    
    def log(self, message, level="info"):
        """Add a log message to the display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level.upper()}: {message}"
        
        self.log_lines.append(log_entry)
        
        # Trim by total characters up to max_log_chars
        try:
            total = 0
            trimmed = []
            for line in reversed(self.log_lines):
                if total + len(line) + 1 > self.max_log_chars:
                    break
                trimmed.append(line)
                total += len(line) + 1
            self.log_lines = list(reversed(trimmed))
        except Exception:
            # Fallback to line-based trimming
            if len(self.log_lines) > self.max_log_lines:
                self.log_lines = self.log_lines[-self.max_log_lines:]
        
        # Update the log display
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        for line in self.log_lines:
            self.log_text.insert(tk.END, line + "\n")
        
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

# Global GUI UI instance
gui_ui = GUIUI()