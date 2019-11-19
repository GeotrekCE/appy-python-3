#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import importlib.util

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def importModule(name, fileName):
    '''Imports module p_name given its absolute file p_name'''
    spec = importlib.util.spec_from_file_location(name, fileName)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Object:
    '''At every place we need an object, but without any requirement on its
       class (methods, attributes,...) we will use this minimalist class.'''

    def __init__(self, **fields):
        for k, v in fields.items(): setattr(self, k, v)

    def __repr__(self):
        '''A compact, string representation of this object for debugging
           purposes.'''
        r = '<O '
        for name, value in self.__dict__.items():
            # Avoid infinite recursion if p_self it auto-referenced
            if value == self: continue
            v = value
            if hasattr(v, '__repr__'):
                try:
                    v = v.__repr__()
                except TypeError:
                    pass
            try:
                r += '%s=%s ' % (name, v)
            except UnicodeDecodeError:
                r += '%s=<encoding problem> ' % name
        return r.strip() + '>'

    def __bool__(self): return bool(self.__dict__)
    def d(self): return self.__dict__
    def get(self, name, default=None): return getattr(self, name, default)
    def __contains__(self, k): return k in self.__dict__
    def keys(self): return self.__dict__.keys()
    def values(self): return self.__dict__.values()
    def items(self): return self.__dict__.items()

    def __setitem__(self, k, v):
        '''Dict-like attribute set'''
        self.__dict__[k] = v

    def __getitem__(self, k):
        '''Dict-like access self[k] must return None if key p_k doesn't exist'''
        return getattr(self, k, None)

    def __delitem__(self, k):
        '''Dict-like attribute removal'''
        del(self.__dict__[k])

    def __getattr__(self, name):
        '''Object access o.<name> must return None if attribute p_name does not
           exist.'''
        return

    def update(self, other):
        '''Set information from p_other (another Object instance or a dict) into
           p_self.'''
        other = other.__dict__ if isinstance(other, Object) else other
        for k, v in other.items(): setattr(self, k, v)

    def clone(self):
        '''Creates a clone from p_self'''
        r = Object()
        r.update(self)
        return r

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Hack:
    '''This class proposes methods for patching some existing code with
       alternative methods.'''

    @staticmethod
    def patch(method, replacement, class_=None):
        '''This method replaces m_method with a p_replacement method, but
           keeps p_method on its class under name
           "_base_<initial_method_name>_". In the patched method, one may use
           Hack.base to call the base method. If p_method is static, you must
           specify its class in p_class_.'''
        # Get the class on which the surgery will take place
        isStatic = class_
        class_ = class_ or method.im_class
        # On this class, store m_method under its "base" name
        name = isStatic and method.func_name or method.im_func.__name__
        baseName = '_base_%s_' % name
        if isStatic:
            # If "staticmethod" isn't called hereafter, the static functions
            # will be wrapped in methods.
            method = staticmethod(method)
            replacement = staticmethod(replacement)
        setattr(class_, baseName, method)
        setattr(class_, name, replacement)

    @staticmethod
    def base(method, class_=None):
        '''Allows to call the base (replaced) method. If p_method is static,
           you must specify its p_class_.'''
        isStatic = class_
        class_ = class_ or method.im_class
        name = isStatic and method.func_name or method.im_func.__name__
        return getattr(class_, '_base_%s_' % name)

    @staticmethod
    def inject(patchClass, class_, verbose=False):
        '''Injects any method or attribute from p_patchClass into class_.'''
        # As a preamble, inject methods and attributes from p_patchClass's base
        # classes, if any.
        for base in patchClass.__bases__:
            Hack.inject(base, class_, verbose=verbose)
        patched = []
        added = []
        # Inject p_patchClass' own methods and attributes
        for name, attr in patchClass.__dict__.items():
            if name.startswith('__'): continue # Ignore special methods
            # Unwrap functions from static methods
            className = attr.__class__.__name__
            if className == 'staticmethod':
                attr = attr.__get__(attr)
                static = True
            else:
                static = False
            # Is this name already defined on p_class_ ?
            if hasattr(class_, name):
                hasAttr = True
                classAttr = getattr(class_, name)
            else:
                hasAttr = False
                classAttr = None
            if hasAttr and (className != 'type') and \
               callable(attr) and callable(classAttr):
                # Patch this method via Hack.patch
                if static:
                    Hack.patch(classAttr, attr, class_)
                else:
                    Hack.patch(classAttr, attr)
                patched.append(name)
            else:
                # Simply replace the static attr or add the new static
                # attribute or method.
                setattr(class_, name, attr)
                added.append(name)
        if verbose:
            pName = patchClass.__name__
            cName = class_.__name__
            print('%d method(s) patched from %s to %s (%s)' % \
                  (len(patched), pName, cName, str(patched)))
            print('%d method(s) and/or attribute(s) added from %s to %s (%s)'%\
                  (len(added), pName, cName, str(added)))
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
