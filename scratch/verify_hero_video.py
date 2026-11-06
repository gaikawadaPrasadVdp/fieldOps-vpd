from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.goto('http://localhost:8000/', wait_until='domcontentloaded')
    
    # Wait for video element
    video = page.wait_for_selector('.fx-showcase-video', timeout=10000)
    
    # Evaluate video attributes and playback
    video_info = page.evaluate('''() => {
        const v = document.querySelector('.fx-showcase-video');
        const header = document.querySelector('.fx-pub-header');
        const vRect = v.getBoundingClientRect();
        const hRect = header.getBoundingClientRect();
        const sources = Array.from(v.querySelectorAll('source')).map(s => s.src);
        return {
            autoplay: v.autoplay,
            muted: v.muted,
            loop: v.loop,
            playsInline: v.playsInline,
            currentSrc: v.currentSrc,
            sources: sources,
            readyState: v.readyState,
            paused: v.paused,
            currentTime: v.currentTime,
            duration: v.duration,
            videoWidth: v.videoWidth,
            videoHeight: v.videoHeight,
            headerBottom: hRect.bottom,
            videoTop: vRect.top,
            videoWidthOnScreen: vRect.width,
            videoHeightOnScreen: vRect.height
        };
    }''')
    
    print('Video info initially:', video_info)
    
    # Wait 2 seconds for playback
    time.sleep(2.0)
    
    playback_check = page.evaluate('''() => {
        const v = document.querySelector('.fx-showcase-video');
        return {
            currentTime: v.currentTime,
            paused: v.paused,
            readyState: v.readyState
        };
    }''')
    print('Playback check after 2s:', playback_check)
    
    # Take screenshot of the hero video below navbar
    page.screenshot(path='scratch/hero_video_verified.png', clip={'x': 0, 'y': 0, 'width': 1400, 'height': 800})
    print('Screenshot saved to scratch/hero_video_verified.png')
    
    browser.close()

