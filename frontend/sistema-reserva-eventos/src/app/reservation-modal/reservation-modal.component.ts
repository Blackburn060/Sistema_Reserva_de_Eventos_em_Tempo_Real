import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-reservation-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, MatInputModule, MatButtonModule, MatIconModule],
  templateUrl: './reservation-modal.component.html',
  styleUrls: ['./reservation-modal.component.css'],
})
export class ReservationModalComponent implements OnInit, OnDestroy {
  @Input() event: any;
  @Output() confirm = new EventEmitter<{ name: string; phone: string }>();
  @Output() cancel = new EventEmitter<void>();

  userName: string = '';
  userPhone: string = '';
  remainingTime: number = 0;
  timer: any;

  ngOnInit() {
    this.remainingTime = this.event.reservationTimeout || 120;
    this.startTimer();
  }

  ngOnDestroy() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }

  startTimer() {
    this.timer = setInterval(() => {
      if (this.remainingTime > 0) {
        this.remainingTime--;
      } else {
        clearInterval(this.timer);
        this.onCancel();
      }
    }, 1000);
  }

  onConfirm() {
    if (this.userName && this.userPhone) {
      this.confirm.emit({ name: this.userName, phone: this.userPhone });
      clearInterval(this.timer);
    }
  }

  onCancel() {
    this.cancel.emit();
    clearInterval(this.timer);
  }

  onClose() {
    this.onCancel();
  }
}
