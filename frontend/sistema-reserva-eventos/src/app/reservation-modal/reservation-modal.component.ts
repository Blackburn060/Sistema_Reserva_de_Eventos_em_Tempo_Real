import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-reservation-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './reservation-modal.component.html',
  styleUrls: ['./reservation-modal.component.css'],
})
export class ReservationModalComponent {
  @Input() event: any;
  @Output() confirm = new EventEmitter<{ name: string; phone: string }>();
  @Output() close = new EventEmitter<void>();

  userName: string = '';
  userPhone: string = '';

  onConfirm() {
    if (this.userName && this.userPhone) {
      this.confirm.emit({ name: this.userName, phone: this.userPhone });
    }
  }

  onClose() {
    this.close.emit();
  }
}
