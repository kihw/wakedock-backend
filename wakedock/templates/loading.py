"""
Loading page templates
"""

from typing import Dict, Any


def get_loading_page(service: Dict[str, Any]) -> str:
    """Generate loading page HTML for a service"""
    service_name = service.get("name", "Service")
    loading_config = service.get("loading_page", {})
    
    title = loading_config.get("title", f"Starting {service_name}...").format(service_name=service_name)
    message = loading_config.get("message", "Please wait while we wake up your service")
    theme = loading_config.get("theme", "dark")
    estimated_time = loading_config.get("estimated_time", 30)
    
    # Theme colors
    if theme == "light":
        bg_color = "#ffffff"
        text_color = "#333333"
        accent_color = "#0066cc"
    else:  # dark theme
        bg_color = "#1a1a1a"
        text_color = "#ffffff"
        accent_color = "#00aaff"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: {bg_color};
                color: {text_color};
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }}
            
            .container {{
                text-align: center;
                max-width: 500px;
                padding: 2rem;
            }}
            
            .logo {{
                font-size: 4rem;
                margin-bottom: 1rem;
                animation: bounce 2s infinite;
            }}
            
            .title {{
                font-size: 2rem;
                font-weight: 600;
                margin-bottom: 1rem;
                color: {accent_color};
            }}
            
            .message {{
                font-size: 1.2rem;
                margin-bottom: 2rem;
                opacity: 0.8;
            }}
            
            .loader {{
                margin: 2rem auto;
                width: 60px;
                height: 60px;
                border: 4px solid rgba(255, 255, 255, 0.1);
                border-top: 4px solid {accent_color};
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }}
            
            .progress-bar {{
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                margin: 2rem 0;
            }}
            
            .progress-fill {{
                height: 100%;
                background: linear-gradient(90deg, {accent_color}, #00ccff);
                border-radius: 3px;
                animation: progress {estimated_time}s ease-out forwards;
                transform: translateX(-100%);
            }}
            
            .status {{
                font-size: 0.9rem;
                opacity: 0.6;
                margin-top: 1rem;
            }}
            
            .dots {{
                animation: dots 1.5s infinite;
            }}
            
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            @keyframes bounce {{
                0%, 20%, 50%, 80%, 100% {{ transform: translateY(0); }}
                40% {{ transform: translateY(-10px); }}
                60% {{ transform: translateY(-5px); }}
            }}
            
            @keyframes progress {{
                0% {{ transform: translateX(-100%); }}
                100% {{ transform: translateX(0); }}
            }}
            
            @keyframes dots {{
                0%, 20% {{ content: ''; }}
                40% {{ content: '.'; }}
                60% {{ content: '..'; }}
                80%, 100% {{ content: '...'; }}
            }}
            
            .particles {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: -1;
            }}
            
            .particle {{
                position: absolute;
                width: 4px;
                height: 4px;
                background: {accent_color};
                border-radius: 50%;
                opacity: 0.6;
                animation: float 6s infinite linear;
            }}
            
            @keyframes float {{
                0% {{
                    transform: translateY(100vh) rotate(0deg);
                    opacity: 0;
                }}
                10% {{
                    opacity: 1;
                }}
                90% {{
                    opacity: 1;
                }}
                100% {{
                    transform: translateY(-100vh) rotate(360deg);
                    opacity: 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="particles" id="particles"></div>
        
        <div class="container">
            <div class="logo">🐳</div>
            <div class="title">{title}</div>
            <div class="message">{message}</div>
            
            <div class="loader"></div>
            
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            
            <div class="status">
                Starting container<span class="dots"></span>
            </div>
        </div>
        
        <script>
            // Create floating particles
            function createParticle() {{
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animationDelay = Math.random() * 6 + 's';
                particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
                document.getElementById('particles').appendChild(particle);
                
                setTimeout(() => {{
                    particle.remove();
                }}, 6000);
            }}
            
            // Create particles periodically
            setInterval(createParticle, 500);
            
            // Auto-refresh page to check if service is ready
            setTimeout(() => {{
                window.location.reload();
            }}, 5000);
            
            // Update status messages
            let statusIndex = 0;
            const statusMessages = [
                'Starting container',
                'Initializing service',
                'Loading application',
                'Almost ready'
            ];
            
            setInterval(() => {{
                const statusEl = document.querySelector('.status');
                statusIndex = (statusIndex + 1) % statusMessages.length;
                statusEl.innerHTML = statusMessages[statusIndex] + '<span class="dots"></span>';
            }}, 3000);
        </script>
    </body>
    </html>
    """
    
    return html
