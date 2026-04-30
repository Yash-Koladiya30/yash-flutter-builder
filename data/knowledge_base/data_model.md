# Data Model Convention

Every data model class follows this shape.

## Template

```dart
import 'package:equatable/equatable.dart';

class Receipt extends Equatable {
  final String id;
  final DateTime date;
  final double amount;
  final String category;
  final String? note;

  const Receipt({
    required this.id,
    required this.date,
    required this.amount,
    required this.category,
    this.note,
  });

  factory Receipt.fromJson(Map<String, dynamic> json) => Receipt(
        id: json['id'] as String,
        date: DateTime.parse(json['date'] as String),
        amount: (json['amount'] as num).toDouble(),
        category: json['category'] as String,
        note: json['note'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date.toIso8601String(),
        'amount': amount,
        'category': category,
        'note': note,
      };

  Receipt copyWith({String? id, DateTime? date, double? amount, String? category, String? note}) =>
      Receipt(
        id: id ?? this.id,
        date: date ?? this.date,
        amount: amount ?? this.amount,
        category: category ?? this.category,
        note: note ?? this.note,
      );

  @override
  List<Object?> get props => [id, date, amount, category, note];
}
```

## Rules

- Always extend `Equatable` — needed for BLoC state comparison.
- All fields `final`. Mutations happen via `copyWith`.
- `const` constructor always.
- `fromJson` / `toJson` for every model — even if we don't call them yet.
- Nullable fields only for truly optional data, never to avoid initialization.
