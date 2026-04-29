# BLoC Pattern (AppAspect Convention)

AppAspect uses `flutter_bloc` for all non-trivial state management.

## Structure

Every feature has:
- `<feature>_event.dart` — sealed classes extending Equatable
- `<feature>_state.dart` — sealed classes extending Equatable
- `<feature>_bloc.dart` — extends `Bloc<Event, State>`

## Example

```dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

sealed class CounterEvent extends Equatable {
  const CounterEvent();
  @override
  List<Object?> get props => [];
}
class Increment extends CounterEvent {}

sealed class CounterState extends Equatable {
  final int value;
  const CounterState(this.value);
  @override
  List<Object?> get props => [value];
}
class CounterInitial extends CounterState {
  const CounterInitial() : super(0);
}

class CounterBloc extends Bloc<CounterEvent, CounterState> {
  CounterBloc() : super(const CounterInitial()) {
    on<Increment>((event, emit) => emit(CounterState(state.value + 1)));
  }
}
```

## Rules

- Never use `setState` once a BLoC exists for the feature.
- States must be `Equatable` — otherwise `BlocBuilder` rebuilds unnecessarily.
- Always emit a new state instance — never mutate.
- Dispose BLoCs via `BlocProvider` — never instantiate manually in widgets.
