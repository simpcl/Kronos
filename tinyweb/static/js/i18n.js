/**
 * Internationalization (i18n) library for Kronos Web UI
 * Supports multiple languages with dynamic text replacement
 */
class I18n {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {};
        this.fallbackLanguage = 'en';
        this.isReady = false;
        // Don't call init() in constructor - we'll call it explicitly
    }

    /**
     * Initialize i18n system
     */
    async init() {
        console.log('🌍 Initializing i18n system...');

        try {
            // Check for saved language preference
            const savedLanguage = localStorage.getItem('kronos-language');
            const detectedLanguage = this.detectBrowserLanguage();
            // Prioritize fallback language (English) unless explicitly saved
            const finalLanguage = savedLanguage || this.fallbackLanguage;

            console.log(`📋 Language detection results:`);
            console.log(`   - Saved language: ${savedLanguage || 'none'}`);
            console.log(`   - Browser language: ${navigator.language || navigator.userLanguage || 'none'}`);
            console.log(`   - Detected language: ${detectedLanguage || 'none'}`);
            console.log(`   - Final language: ${finalLanguage}`);

            this.currentLanguage = finalLanguage;

            // Load all language files
            console.log('🔄 Starting translation file loading...');
            const loadSuccess = await this.loadTranslations();

            if (!loadSuccess) {
                console.warn('⚠️ No translation files were loaded, using fallback');
            }

            // Apply translations to the page
            console.log('🔄 Applying initial translations...');
            this.applyTranslations();

            this.isReady = true;
            console.log('✅ i18n system initialized successfully');
            console.log(`🌐 Current active language: ${this.currentLanguage}`);

        } catch (error) {
            console.error('❌ i18n initialization failed:', error);
            // Still mark as ready to prevent infinite waiting
            this.isReady = true;
            console.warn('⚠️ Marking i18n as ready despite errors to prevent deadlock');
        }
    }

    /**
     * Detect browser language
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;

        // Map browser language codes to our supported languages
        const langMap = {
            'zh': 'zh',
            'zh-CN': 'zh',
            'zh-TW': 'zh',
            'en': 'en',
            'en-US': 'en'
        };

        return langMap[browserLang] || null;
    }

    /**
     * Load all translation files
     */
    async loadTranslations() {
        const supportedLanguages = ['en', 'zh'];
        console.log(`📚 Loading translations for: ${supportedLanguages.join(', ')}`);

        // Try to determine the current port
        const currentPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
        const baseUrl = `${window.location.protocol}//${window.location.hostname}:${currentPort}`;

        let loadCount = 0;
        for (const lang of supportedLanguages) {
            try {
                const url = `${baseUrl}/static/js/i18n/${lang}.json`;
                console.log(`📖 Loading ${lang} translations from: ${url}`);

                const response = await fetch(url);
                if (response.ok) {
                    this.translations[lang] = await response.json();
                    loadCount++;
                    console.log(`✅ Successfully loaded ${lang} translations (${loadCount}/${supportedLanguages.length})`);
                } else {
                    console.error(`❌ Failed to load ${lang} translations: HTTP ${response.status}`);
                }
            } catch (error) {
                console.error(`❌ Failed to load ${lang} translations:`, error);
            }
        }

        // Ensure fallback language is loaded
        if (!this.translations[this.fallbackLanguage]) {
            console.error('❌ Fallback language not loaded! Creating minimal fallback...');
            // Create minimal fallback translations to prevent system failure
            this.translations[this.fallbackLanguage] = {
                title: "Kronos Financial Prediction Web UI",
                subtitle: "AI-based financial K-line data prediction analysis platform"
            };
        } else {
            console.log(`✅ Fallback language (${this.fallbackLanguage}) loaded successfully`);
        }

        console.log(`📋 Translation loading complete: ${loadCount}/${supportedLanguages.length} files loaded`);
        console.log(`📋 Available languages: ${Object.keys(this.translations).join(', ')}`);

        return loadCount > 0; // Return success status
    }

    /**
     * Get translated text by key
     */
    t(key, params = {}) {
        // Try current language first
        let translation = this.getNestedValue(this.translations[this.currentLanguage], key);

        // Fallback to fallback language if translation not found
        if (!translation) {
            translation = this.getNestedValue(this.translations[this.fallbackLanguage], key);
        }

        // Return key if no translation found
        if (!translation) {
            console.warn(`Translation not found for key: ${key}`);
            return key;
        }

        // Replace parameters in translation
        return this.replaceParams(translation, params);
    }

    /**
     * Get nested value from object using dot notation
     */
    getNestedValue(obj, key) {
        return key.split('.').reduce((current, prop) => {
            return current && current[prop] !== undefined ? current[prop] : null;
        }, obj);
    }

    /**
     * Replace parameters in translation string
     */
    replaceParams(text, params) {
        if (typeof text !== 'string') return text;

        return text.replace(/\{(\w+)\}/g, (match, param) => {
            return params[param] !== undefined ? params[param] : match;
        });
    }

    /**
     * Apply translations to all elements with data-i18n attribute
     */
    applyTranslations() {
        console.log(`🔄 Applying translations for language: ${this.currentLanguage}`);

        const elements = document.querySelectorAll('[data-i18n]');
        console.log(`📝 Found ${elements.length} elements to translate`);

        elements.forEach((element, index) => {
            const key = element.getAttribute('data-i18n');
            const oldText = element.tagName === 'OPTION' ? element.textContent : (element.value || element.textContent);

            // Handle parameters for dynamic content
            let params = {};
            if (element.hasAttribute('data-i18n-params')) {
                try {
                    params = JSON.parse(element.getAttribute('data-i18n-params'));
                } catch (error) {
                    console.warn(`⚠️ Failed to parse i18n params for element ${key}:`, error);
                }
            }

            const translation = this.t(key, params);

            console.log(`🔄 Translating element ${index + 1}/${elements.length}: ${key} = "${oldText}" -> "${translation}"`);

            // Handle different element types
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                if (element.type === 'submit' || element.type === 'button') {
                    element.value = translation;
                } else {
                    element.placeholder = translation;
                }
            } else if (element.tagName === 'OPTION') {
                element.textContent = translation;
            } else {
                element.textContent = translation;
            }

            // Handle placeholder attribute
            if (element.hasAttribute('data-i18n-placeholder')) {
                const placeholderKey = element.getAttribute('data-i18n-placeholder');
                element.placeholder = this.t(placeholderKey);
            }
        });

        // Update page title
        const titleElement = document.querySelector('title');
        if (titleElement) {
            const oldTitle = titleElement.textContent;
            const newTitle = this.t('title');
            titleElement.textContent = newTitle;
            console.log(`🔄 Title: "${oldTitle}" -> "${newTitle}"`);
        }

        console.log('✅ Translations applied successfully');
    }

    /**
     * Switch to a different language
     */
    async switchLanguage(language) {
        console.log(`🔄 Switching language to: ${language}`);

        if (!this.translations[language]) {
            console.error(`❌ Language ${language} not supported. Available: ${Object.keys(this.translations).join(', ')}`);
            return false;
        }

        this.currentLanguage = language;
        localStorage.setItem('kronos-language', language);
        this.applyTranslations();

        // Dispatch language change event
        window.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: language }
        }));

        console.log(`✅ Language switched to ${language} successfully`);
        return true;
    }

    /**
     * Get current language
     */
    getCurrentLanguage() {
        return this.currentLanguage;
    }

    /**
     * Get available languages
     */
    getAvailableLanguages() {
        return Object.keys(this.translations).map(lang => ({
            code: lang,
            name: this.getLanguageName(lang)
        }));
    }

    /**
     * Get language display name
     */
    getLanguageName(code) {
        const names = {
            'en': 'English',
            'zh': '中文'
        };
        return names[code] || code;
    }

    /**
     * Format message with dynamic parameters
     */
    formatMessage(key, params = {}) {
        return this.t(key, params);
    }
}

// Global i18n instance
let i18n;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 DOM Content Loaded, starting i18n initialization...');
    try {
        i18n = new I18n();
        window.i18n = i18n; // Set global reference immediately
        window.I18n = I18n;

        console.log('📚 Created i18n instance, calling init...');
        await i18n.init();
        console.log('✅ i18n initialization completed');
    } catch (error) {
        console.error('❌ i18n initialization failed:', error);
    }
});