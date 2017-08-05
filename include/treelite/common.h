/*!
 * Copyright by 2017 Contributors
 * \file common.h
 * \brief Some useful utilities
 * \author Philip Cho
 */
#ifndef TREELITE_COMMON_H_
#define TREELITE_COMMON_H_

#include <memory>
#include <dmlc/logging.h>
#include <treelite/base.h>

namespace treelite {
namespace common {

class Cloneable {
 public:
  virtual ~Cloneable() = default;
  virtual Cloneable* clone() const = 0;
  virtual Cloneable* move_clone() = 0;
};

#define CLONEABLE_BOILERPLATE(className) \
  explicit className(const className& other) = default;  \
  explicit className(className&& other) = default;  \
  Cloneable* clone() const override {  \
    return new className(*this);  \
  }  \
  Cloneable* move_clone() override {  \
    return new className(std::move(*this));  \
  }

template <typename T>
class DeepCopyUniquePtr {
 public:
  static_assert(std::is_base_of<Cloneable, T>::value,
                "DeepCopyUniquePtr requires a Cloneable type");
  ~DeepCopyUniquePtr() {}

  explicit DeepCopyUniquePtr(const T& other)
    : ptr(dynamic_cast<T*>(other.clone())) {}
    // downcasting is okay here because the other object is certainly of type T
  explicit DeepCopyUniquePtr(T&& other)
    : ptr(dynamic_cast<T*>(other.move_clone())) {}
  explicit DeepCopyUniquePtr(const DeepCopyUniquePtr<T>& other)
    : ptr(dynamic_cast<T*>(other.ptr->clone())) {}
  explicit DeepCopyUniquePtr(DeepCopyUniquePtr<T>&& other)
    : ptr(std::move(other.ptr)) {}

  inline T& operator*() {
    return *ptr;
  }
  const inline T& operator*() const {
    return *ptr;
  }
  T* operator->() {
    return ptr.operator->();
  }
  const T* operator->() const {
    return ptr.operator->();
  }

 private:
  std::unique_ptr<T> ptr;
};

template <typename T>
inline T&& MoveUniquePtr(const std::unique_ptr<T>& ptr) {
  return std::move(*ptr.get());
}

inline void WrapText(std::ostringstream* p_stm, size_t* p_length,
                     const std::string& str, size_t textwidth) {
  std::ostringstream& stm = *p_stm;
  size_t& length = *p_length;
  if (length + str.length() + 2 <= textwidth) {
    stm << str << ", ";
    length += str.length() + 2;
  } else {
    stm << "\n  " << str << ", ";
    length = str.length() + 4;
  }
}

template<class Iter, class T>
Iter binary_search(Iter begin, Iter end, const T& val)
{
  Iter i = std::lower_bound(begin, end, val);
  if (i != end && !(val < *i)) {
    return i;  // found
  } else {
    return end;  // not found
  }
}

inline std::string FloatToString(tl_float value) {
  std::ostringstream oss;
  oss << value;
  return oss.str();
}

}  // namespace common
}  // namespace treelite
#endif  // TREELITE_COMMON_H_
