import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./inbox/inbox').then((m) => m.Inbox), title: 'Inbox – Clearline' },
  { path: 'cases/:id', loadComponent: () => import('./case/case-page').then((m) => m.CasePage), title: 'Case – Clearline' },
  { path: 'quality', loadComponent: () => import('./quality/quality').then((m) => m.Quality), title: 'Quality – Clearline' },
  { path: 'operations', loadComponent: () => import('./operations/operations').then((m) => m.Operations), title: 'Operations – Clearline' },
  { path: 'about', loadComponent: () => import('./about/about').then((m) => m.About), title: 'About – Clearline' },
  { path: '**', redirectTo: '' },
];
