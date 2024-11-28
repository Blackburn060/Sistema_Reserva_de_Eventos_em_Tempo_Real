import { Routes } from '@angular/router';
import { EventListComponent } from './event-list/event-list.component';
import { AdminPanelComponent } from './admin-panel/admin-panel.component';

export const routes: Routes = [
  { path: 'eventos', component: EventListComponent },
  { path: 'admin', component: AdminPanelComponent },
  { path: '**', redirectTo: 'eventos' },
];