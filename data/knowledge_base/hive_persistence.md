# Hive Local Persistence

We use Hive for local storage of small/medium datasets. SQL is only used when
queries need joins or aggregation.

## Initialisation

```dart
import 'package:hive_flutter/hive_flutter.dart';

Future<void> main() async {
  await Hive.initFlutter();
  await Hive.openBox<String>('settings');
  await Hive.openBox<Map>('receipts');
  runApp(const MyApp());
}
```

## Usage

```dart
final box = Hive.box<Map>('receipts');
await box.put(receipt.id, receipt.toJson());

final stored = box.get(id);
if (stored != null) {
  final receipt = Receipt.fromJson(Map<String, dynamic>.from(stored));
}
```

## Rules

- Open boxes during `main()` before `runApp` — never lazily inside widgets.
- Store `Map<String, dynamic>` via `toJson`/`fromJson`, not custom TypeAdapters,
  unless profile-profile reuse demands it.
- Close boxes in dispose of long-lived BLoCs when appropriate.
