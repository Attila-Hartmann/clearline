import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  protected readonly nav = [
    { path: '/', label: 'Inbox', exact: true },
    { path: '/quality', label: 'Quality', exact: false },
    { path: '/operations', label: 'Operations', exact: false },
    { path: '/about', label: 'How it works', exact: false },
  ];
}
