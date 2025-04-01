from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class UMLClass(Base):
    __tablename__ = 'uml_class'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    package_name = Column(String)
    is_abstract = Column(Boolean)
    is_interface = Column(Boolean)
    annotations = Column(Text)
    files = Column(Text)
    dom_id = Column(Text)
    display_name = Column(Text)
    summary = Column(Text)
    comments = Column(Text)

    properties = relationship("UMLProperty", back_populates="uml_class")
    methods = relationship("UMLMethod", back_populates="uml_class")

class UMLProperty(Base):
    __tablename__ = 'uml_property'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('uml_class.id'))
    name = Column(String)
    data_type = Column(String)
    visibility = Column(String)
    is_static = Column(Boolean)
    is_final = Column(Boolean)
    source_line = Column(Integer)
    dom_id = Column(Text)
    annotations = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    uml_class = relationship("UMLClass", back_populates="properties")

class UMLMethod(Base):
    __tablename__ = 'uml_method'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('uml_class.id'))
    name = Column(String)
    dom_id = Column(Text)
    return_type = Column(String)
    visibility = Column(String)
    is_static = Column(Boolean)
    is_abstract = Column(Boolean)
    starting_line = Column(Integer)
    ending_line = Column(Integer)
    source = Column(Text)
    annotations = Column(Text)
    display_name = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    uml_class = relationship("UMLClass", back_populates="methods")
    parameters = relationship("UMLParameter", back_populates="method")

class UMLParameter(Base):
    __tablename__ = 'uml_parameter'
    id = Column(Integer, primary_key=True)
    method_id = Column(Integer, ForeignKey('uml_method.id'))
    name = Column(String)
    dom_id = Column(Text)
    data_type = Column(String)
    display_name = Column(Text)
    annotations = Column(Text)
    comments = Column(Text)
    summary = Column(Text)

    method = relationship("UMLMethod", back_populates="parameters")

class UMLRelationship(Base):
    __tablename__ = "uml_relationship"
    id = Column(Integer, primary_key=True)
    source = Column(String)
    target = Column(String)
    name = Column(String)
    type = Column(String)
    
class UMLPackage(Base):
    __tablename__ = "uml_package"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    parent = Column(String)
    

# === Connect and Extract Data ===

engine = create_engine('sqlite:///uml-data.db')
Session = sessionmaker(bind=engine)
session = Session()

# # Print UML classes and related elements
# for uml_class in session.query(UMLClass).all():
#     print(f"\n📦 Class: {uml_class.name} (Package: {uml_class.package_name})")
    
#     for prop in uml_class.properties:
#         print(f"  🔸 Property: {prop.name} ({prop.data_type}) [{prop.visibility}]")

#     for method in uml_class.methods:
#         print(f"  🔹 Method: {method.name} -> {method.return_type} [{method.visibility}]")
#         for param in method.parameters:
#             print(f"    🔻 Param: {param.name}: {param.data_type}")

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
import json
from sqlalchemy import or_
def get_classes(package_name: str):
    result = {
        "type": "class",
        "classes": [],
        "relationships":[]
    }

    if not package_name:
        classes = session.query(UMLClass).all()
        relationships = session.query(UMLRelationship).all()    
    else:
        classes = session.query(UMLClass).filter(UMLClass.package_name == package_name).all()
        class_names = [f"{cls.package_name}.{cls.name}" for cls in classes]
        relationships = session.query(UMLRelationship).filter( or_( UMLRelationship.source.in_(class_names), UMLRelationship.target.in_(class_names) )).all()
    
    for cls in classes:
        class_dict = {
            "type": "class",
            "annotations": "",#json.loads(cls.annotations) if cls.annotations else [],
            "id": f"{cls.package_name}.{cls.name}",
            "domId": cls.dom_id or "",
            "name": cls.name,
            "package": cls.package_name,
            "seleced": False,
            "style": "",
            "generatedContent": "",
            "files": json.loads(cls.files) if cls.files else [],
            "isAbstract": bool(cls.is_abstract),
            "isInterface": bool(cls.is_interface),
            "properties": [],
            "methods": []
        }

        for prop in cls.properties:
            class_dict["properties"].append({
                "name": prop.name,
                "dataType": prop.data_type,
                "annotations": "",#json.loads(prop.annotations) if prop.annotations else [],
                "visibility": prop.visibility,
                "isStatic": bool(prop.is_static),
                "isFinal": bool(prop.is_final)
            })

        for method in cls.methods:
            method_dict = {
                "name": method.name,
                "returnType": method.return_type,
                "annotations": "",#json.loads(method.annotations) if method.annotations else [],
                "visibility": method.visibility,
                "isStatic": bool(method.is_static),
                "isAbstract": bool(method.is_abstract),
                "parameters": []
            }

            for param in method.parameters:
                method_dict["parameters"].append({
                    "name": param.name,
                    "dataType": param.data_type,
                    "annotations": json.loads(param.annotations) if param.annotations else []
                })

            class_dict["methods"].append(method_dict)

        result["classes"].append(class_dict)
    for rls in relationships:
        rls_dict = {
            "id": f"{rls.id}",
            # "domId": rls.dom_id or "",
            "name": rls.name,
            "source": rls.source,
            "target": rls.target,
            "type": rls.type
        }
        result["relationships"].append(rls_dict)
    session.close()
    return result
# output = json.dumps(get_classes_by_package("org.keycloak.themeverifier"), indent=2)


def get_packages(package_name: str):
    result = {
        "type": "package",
        "id": package_name or "",
        "name": package_name.split(".")[-1] if package_name else "",
        "packages": [],
        "classes": [],
        "relationships": []
    }

    # 1. Fetch classes and subpackages
    if not package_name:
        classes = session.query(UMLClass).filter(UMLClass.package_name.is_(None)).all()
        subpackages = session.query(UMLPackage).filter(UMLPackage.parent.is_(None)).all()
    else:
        classes = session.query(UMLClass).filter(UMLClass.package_name == package_name).all()
        subpackages = session.query(UMLPackage).filter(UMLPackage.parent == package_name).all()

    # 2. Build class → package map
    package_scope_class_map = {}
    all_package_names = set()

    for cls in classes:
        fqcn = f"{cls.package_name}.{cls.name}" if cls.package_name else cls.name
        pkg = cls.package_name or ""
        package_scope_class_map[fqcn] = pkg
        all_package_names.add(pkg)

    for subpkg in subpackages:
        full_pkg = f"{subpkg.parent}.{subpkg.name}" if subpkg.parent else subpkg.name
        has_children = session.query(UMLPackage).filter(UMLPackage.parent == full_pkg).first() is not None
        all_package_names.add(full_pkg)

        subpkg_dict = {
            "type": "package",  
            "annotation": "",
            "id": full_pkg,
            "name": subpkg.name,
            "package": subpkg.parent or "",
            "on_click": f"packages?package={full_pkg}" if has_children else f"classes?package={full_pkg}",
            "subpackages": [],
            "classes": []
        }
        result["packages"].append(subpkg_dict)

        subpkg_classes = session.query(UMLClass).filter(UMLClass.package_name == full_pkg).all()
        for cls in subpkg_classes:
            fqcn = f"{cls.package_name}.{cls.name}"
            package_scope_class_map[fqcn] = cls.package_name

    # 3. Add only current package’s own classes
    for cls in classes:
        result["classes"].append({
            "type": "class",
            "annotation": "",
            "id": f"{cls.package_name}.{cls.name}" if cls.package_name else cls.name,
            "name": cls.name,
            "package": cls.package_name or ""
        })

    # 4. Elevate class-level relationships to package-level
    all_relationships = session.query(UMLRelationship).all()
    seen_package_pairs = set()

    for r in all_relationships:
        src_pkg = package_scope_class_map.get(r.source)
        tgt_pkg = package_scope_class_map.get(r.target)

        if src_pkg and tgt_pkg and src_pkg != tgt_pkg:
            key = (src_pkg, tgt_pkg)
            if key not in seen_package_pairs:
                seen_package_pairs.add(key)
                result["relationships"].append({
                    "id": f"{src_pkg}->{tgt_pkg}",
                    "label": r.name or "",
                    "source": src_pkg,
                    "target": tgt_pkg,
                    "type": r.type
                })

    session.close()
    return result