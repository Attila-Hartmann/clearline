import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideOptimus } from '@openng/optimus-ui/config';
import { definePreset } from '@openng/optimus-ui-themes';
import Aura from '@openng/optimus-ui-themes/aura';

import { routes } from './app.routes';

// Aura with a Danube-teal primary scale; everything else stays quiet.
const Danube = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eaf3f5', 100: '#cfe3e8', 200: '#a3c9d2', 300: '#6fa9b7', 400: '#3f8799',
      500: '#0f5e73', 600: '#0d5466', 700: '#0b4757', 800: '#093a47', 900: '#072d37', 950: '#041c23',
    },
  },
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withFetch()),
    provideRouter(routes, withComponentInputBinding()),
    provideOptimus({ theme: { preset: Danube, options: { darkModeSelector: false } } }),
  ],
};
